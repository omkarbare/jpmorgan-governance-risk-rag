from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evals" / "datasets" / "governance_rag_v1.jsonl"
RESULTS_DIR = ROOT / "evals" / "results"

DEFAULT_API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT = float(os.getenv("RAG_EVAL_TIMEOUT_SEC", "75"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number} in {path}") from error
    return records


def normalize_doc_type(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def request_api(
    client: httpx.Client,
    api_url: str,
    record: dict[str, Any],
    groq_api_key: str | None,
) -> tuple[int | None, dict[str, Any] | None, str | None, int]:
    headers = {"Content-Type": "application/json"}

    if groq_api_key:
        headers["x-groq-api-key"] = groq_api_key

    started_at = time.perf_counter()

    try:
        response = client.post(
            f"{api_url.rstrip('/')}/ask",
            headers=headers,
            json={"query": record["query"], "top_k": 5},
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)

        try:
            body = response.json()
        except json.JSONDecodeError:
            body = None

        if response.status_code >= 400:
            detail = body.get("detail") if isinstance(body, dict) else response.text
            return response.status_code, body, str(detail), elapsed_ms

        return response.status_code, body, None, elapsed_ms

    except httpx.HTTPError as error:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return None, None, str(error), elapsed_ms


def evaluate_record(
    record: dict[str, Any],
    status_code: int | None,
    body: dict[str, Any] | None,
    request_error: str | None,
    wall_latency_ms: int,
) -> dict[str, Any]:
    expected_behavior = record.get("expected_behavior", "answer")
    expected_status = record.get("expected_guardrail_status")
    expected_reason = record.get("expected_guardrail_reason")
    expected_doc_types = {
        normalize_doc_type(value)
        for value in record.get("expected_doc_types", [])
    }
    must_have_citations = bool(record.get("must_have_citations", False))
    must_include = [str(item).lower() for item in record.get("must_include", [])]

    result: dict[str, Any] = {
        "id": record["id"],
        "category": record.get("category", ""),
        "query": record["query"],
        "expected_behavior": expected_behavior,
        "status_code": status_code,
        "request_error": request_error,
        "wall_latency_ms": wall_latency_ms,
        "passed": False,
        "checks": {},
    }

    if request_error or not body:
        result["checks"] = {
            "api_success": False,
            "expected_behavior": False,
        }
        result["failure_reason"] = request_error or "No JSON body returned"
        return result

    answer = str(body.get("answer", ""))
    citations = body.get("citations", []) or []
    actual_guardrail_status = body.get("guardrail_status")
    actual_guardrail_reason = body.get("guardrail_reason")
    actual_doc_types = {
        normalize_doc_type(citation.get("doc_type"))
        for citation in citations
    }
    citation_indices = [
        citation.get("citation_index")
        for citation in citations
        if isinstance(citation.get("citation_index"), int)
    ]

    answer_has_citation_markers = any(
        f"[{index}]" in answer for index in citation_indices
    )

    checks: dict[str, bool] = {}
    checks["api_success"] = status_code == 200
    checks["guardrail_status"] = (
        actual_guardrail_status == expected_status
        if expected_status
        else True
    )
    checks["guardrail_reason"] = (
        actual_guardrail_reason == expected_reason
        if expected_reason
        else True
    )

    if expected_behavior == "blocked":
        checks["expected_behavior"] = (
            actual_guardrail_status == "blocked"
            and len(citations) == 0
            and body.get("model") == "none"
        )
    elif expected_behavior == "insufficient_evidence":
        lower_answer = answer.lower()
        checks["expected_behavior"] = any(
            phrase in lower_answer
            for phrase in [
                "could not find sufficient evidence",
                "insufficient evidence",
                "cannot determine",
                "not enough evidence",
            ]
        )
    else:
        checks["expected_behavior"] = (
            actual_guardrail_status == "passed"
            and len(answer.strip()) > 20
        )

    checks["citation_presence"] = (
        bool(citations) and answer_has_citation_markers
        if must_have_citations
        else True
    )

    checks["expected_document_hit"] = (
        bool(actual_doc_types.intersection(expected_doc_types))
        if expected_doc_types
        else True
    )

    checks["required_phrase"] = all(
        phrase in answer.lower()
        for phrase in must_include
    )

    checks["citations_well_formed"] = all(
        isinstance(index, int) and index >= 1
        for index in citation_indices
    )

    result.update(
        {
            "request_id": body.get("request_id"),
            "answer": answer,
            "answer_preview": answer[:500],
            "guardrail_status": actual_guardrail_status,
            "guardrail_reason": actual_guardrail_reason,
            "api_latency_ms": body.get("latency_ms"),
            "retrieval_count": body.get("retrieval_count"),
            "citation_count": body.get("citation_count"),
            "model": body.get("model"),
            "actual_doc_types": sorted(actual_doc_types),
            "citation_indices": citation_indices,
            "checks": checks,
        }
    )

    result["passed"] = all(checks.values())
    if not result["passed"]:
        failed = [name for name, value in checks.items() if not value]
        result["failure_reason"] = ", ".join(failed)

    return result


def percentile(values: list[int], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def build_summary(
    results: list[dict[str, Any]],
    dataset_path: Path,
    api_url: str,
) -> dict[str, Any]:
    total = len(results)
    passed = sum(bool(result["passed"]) for result in results)
    blocked_tests = [
        result
        for result in results
        if result["expected_behavior"] == "blocked"
    ]
    answered_tests = [
        result
        for result in results
        if result["expected_behavior"] == "answer"
    ]

    latencies = [
        int(result["api_latency_ms"])
        for result in results
        if isinstance(result.get("api_latency_ms"), int)
    ]

    citation_tests = [
        result
        for result in answered_tests
        if result["checks"].get("citation_presence") is not None
    ]

    document_hit_tests = [
        result
        for result in answered_tests
        if result["checks"].get("expected_document_hit") is not None
    ]

    def rate(items: list[dict[str, Any]], key: str) -> float | None:
        if not items:
            return None
        return round(
            sum(bool(item["checks"].get(key)) for item in items) / len(items),
            4,
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "api_url": api_url,
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "guardrail_block_rate": rate(blocked_tests, "expected_behavior"),
        "citation_presence_rate": rate(citation_tests, "citation_presence"),
        "expected_document_hit_rate": rate(
            document_hit_tests,
            "expected_document_hit",
        ),
        "latency_ms": {
            "count": len(latencies),
            "mean": round(statistics.mean(latencies), 2) if latencies else None,
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "p95": round(percentile(latencies, 0.95), 2)
            if latencies
            else None,
            "max": max(latencies) if latencies else None,
        },
        "failed_case_ids": [
            result["id"] for result in results if not result["passed"]
        ],
    }


def write_results(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_path = RESULTS_DIR / "latest_results.jsonl"
    csv_path = RESULTS_DIR / "latest_results.csv"
    summary_path = RESULTS_DIR / "latest_summary.json"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")

    csv_rows: list[dict[str, Any]] = []
    for result in results:
        checks = result.get("checks", {})
        csv_rows.append(
            {
                "id": result.get("id"),
                "category": result.get("category"),
                "passed": result.get("passed"),
                "failure_reason": result.get("failure_reason", ""),
                "expected_behavior": result.get("expected_behavior"),
                "guardrail_status": result.get("guardrail_status", ""),
                "guardrail_reason": result.get("guardrail_reason", ""),
                "api_latency_ms": result.get("api_latency_ms", ""),
                "wall_latency_ms": result.get("wall_latency_ms", ""),
                "retrieval_count": result.get("retrieval_count", ""),
                "citation_count": result.get("citation_count", ""),
                "actual_doc_types": "|".join(result.get("actual_doc_types", [])),
                "api_success": checks.get("api_success"),
                "expected_behavior_check": checks.get("expected_behavior"),
                "citation_presence": checks.get("citation_presence"),
                "expected_document_hit": checks.get("expected_document_hit"),
                "required_phrase": checks.get("required_phrase"),
                "query": result.get("query"),
            }
        )

    if csv_rows:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(f"\nWrote results: {jsonl_path}")
    print(f"Wrote CSV:     {csv_path}")
    print(f"Wrote summary: {summary_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the guarded JPMorgan governance/risk RAG API."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to JSONL evaluation dataset.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="FastAPI base URL.",
    )
    parser.add_argument(
        "--groq-api-key",
        default=os.getenv("GROQ_API_KEY"),
        help=(
            "Optional session Groq key. Prefer GROQ_API_KEY environment variable "
            "instead of passing a key on the command line."
        ),
    )
    parser.add_argument(
        "--only-category",
        default=None,
        help="Run only records with this category.",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Dataset does not exist: {args.dataset}", file=sys.stderr)
        return 2

    records = read_jsonl(args.dataset)
    if args.only_category:
        records = [
            record
            for record in records
            if record.get("category") == args.only_category
        ]

    if not records:
        print("No evaluation records selected.", file=sys.stderr)
        return 2

    print(f"Running {len(records)} evaluation cases against {args.api_url}")

    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        for position, record in enumerate(records, start=1):
            print(f"[{position}/{len(records)}] {record['id']} — {record['category']}")
            status_code, body, request_error, wall_latency_ms = request_api(
                client=client,
                api_url=args.api_url,
                record=record,
                groq_api_key=args.groq_api_key,
            )
            result = evaluate_record(
                record=record,
                status_code=status_code,
                body=body,
                request_error=request_error,
                wall_latency_ms=wall_latency_ms,
            )
            results.append(result)
            icon = "PASS" if result["passed"] else "FAIL"
            print(f"  {icon} | {result.get('failure_reason', '')}")

    summary = build_summary(
        results=results,
        dataset_path=args.dataset,
        api_url=args.api_url,
    )
    write_results(results, summary)

    print("\n=== Evaluation Summary ===")
    print(json.dumps(summary, indent=2))

    return 0 if summary["failed_cases"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
