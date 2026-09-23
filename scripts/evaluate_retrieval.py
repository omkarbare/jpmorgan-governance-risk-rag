from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evals" / "datasets" / "governance_rag_v1.jsonl"
DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 60.0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def run_retrieval(
    client: httpx.Client,
    api_url: str,
    query: str,
    top_k: int,
    method: str,
) -> list[dict[str, Any]]:
    resp = client.post(
        f"{api_url.rstrip('/')}/retrieve",
        json={"query": query, "top_k": top_k, "method": method},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])


def compute_hit_and_mrr(
    results: list[dict[str, Any]],
    golden_chunk_prefix: str,
    golden_doc_id: str,
) -> tuple[bool, float]:
    """
    Returns (hit_at_k, reciprocal_rank).
    Hit if any result matches golden doc/chunk prefix.
    RR = 1/rank of first matching result, or 0 if no match.
    """
    if not golden_chunk_prefix and not golden_doc_id:
        # Unanswerable or no golden; treat as not applicable
        return True, 1.0

    hit = False
    rr = 0.0

    for idx, res in enumerate(results):
        chunk_id = (res.get("chunk_id") or "").lower()
        doc_id = (res.get("doc_id") or "").lower()
        golden_prefix = (golden_chunk_prefix or "").lower()
        golden_doc = (golden_doc_id or "").lower()

        matches = (
            (not golden_prefix or golden_prefix in chunk_id)
            and (not golden_doc or golden_doc == doc_id)
        )

        if matches:
            hit = True
            rr = 1.0 / (idx + 1)
            break

    return hit, rr


def evaluate_method(
    client: httpx.Client,
    api_url: str,
    records: list[dict[str, Any]],
    method: str,
    top_k: int,
) -> dict[str, Any]:
    hits = 0
    total = 0
    rr_sum = 0.0

    for rec in records:
        golden_doc_id = rec.get("golden_doc_id", "")
        golden_prefix = rec.get("golden_chunk_prefix", "")
        category = rec.get("category", "")

        if category == "unanswerable":
            # Skip retrieval metrics for unanswerable questions
            continue

        results = run_retrieval(client, api_url, rec["query"], top_k, method)
        hit, rr = compute_hit_and_mrr(results, golden_prefix, golden_doc_id)

        hits += int(hit)
        rr_sum += rr
        total += 1

    hit_rate = hits / total if total else 0.0
    mrr = rr_sum / total if total else 0.0

    return {
        "method": method,
        "top_k": top_k,
        "questions_evaluated": total,
        "hits": hits,
        "hit_rate": round(hit_rate, 4),
        "mrr": round(mrr, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    records = read_jsonl(args.dataset)

    methods = ["dense", "sparse", "hybrid"]

    results = []
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        for method in methods:
            print(f"Evaluating retrieval method: {method}")
            metrics = evaluate_method(client, args.api_url, records, method, args.top_k)
            results.append(metrics)
            print(json.dumps(metrics, indent=2))

    summary = {
        "api_url": args.api_url,
        "dataset": str(args.dataset),
        "top_k": args.top_k,
        "methods": results,
    }

    out_path = ROOT / "evals" / "results" / "retrieval_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(f"\nWrote retrieval summary to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
