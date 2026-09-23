from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evals" / "datasets" / "governance_rag_v1.jsonl"
DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 75.0
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4o-mini")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def call_judge(
    client: httpx.Client,
    query: str,
    answer: str,
    reference: str | None,
    category: str,
) -> dict[str, Any]:
    """
    Simple LLM-as-judge for answer correctness.
    Returns {correctness: "correct"|"partial"|"incorrect", rationale: str}.
    """
    if not reference:
        # For unanswerable/adversarial, use rule-based checks instead
        return {"correctness": "partial", "rationale": "No reference answer provided"}

    system_prompt = (
        "You are an evaluator of a RAG assistant about JPMorgan governance, risk, and conduct. "
        "Grade the assistant's answer as 'correct', 'partial', or 'incorrect' compared to the reference. "
        "Be strict about factual accuracy and grounding."
    )

    user_prompt = (
        f"Question: {query}\n\n"
        f"Reference answer: {reference}\n\n"
        f"Assistant answer: {answer}\n\n"
        "Return JSON: {\"correctness\": \"correct|partial|incorrect\", \"rationale\": \"...\"}"
    )

    resp = client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": JUDGE_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        },
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"correctness": "partial", "rationale": "Judge parsing failed"}


def evaluate_generation(
    api_url: str,
    records: list[dict[str, Any]],
    groq_api_key: str | None,
) -> list[dict[str, Any]]:
    results = []
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        for rec in records:
            resp = client.post(
                f"{api_url.rstrip('/')}/ask",
                headers={"x-groq-api-key": groq_api_key} if groq_api_key else {},
                json={"query": rec["query"], "top_k": 5},
                timeout=DEFAULT_TIMEOUT,
            )
            data = resp.json()

            answer = data.get("answer", "")
            citations = data.get("citations", [])
            guardrail_status = data.get("guardrail_status")
            expected_behavior = rec.get("expected_behavior")

            correctness = "partial"
            rationale = ""

            if expected_behavior == "insufficient_evidence":
                lower = answer.lower()
                refused = any(
                    p in lower
                    for p in [
                        "could not find sufficient evidence",
                        "insufficient evidence",
                        "cannot determine",
                        "not enough evidence",
                        "could not produce a properly cited answer",
                    ]
                )
                correctness = "correct" if refused else "incorrect"
                rationale = "Refusal check for unanswerable question"
            elif expected_behavior == "blocked":
                correctness = (
                    "correct"
                    if guardrail_status == "blocked"
                    else "incorrect"
                )
                rationale = "Guardrail block check"
            else:
                # Use LLM judge if OPENAI_API_KEY is set
                if os.getenv("OPENAI_API_KEY"):
                    judge_client = httpx.Client(timeout=DEFAULT_TIMEOUT)
                    judgment = call_judge(
                        judge_client,
                        rec["query"],
                        answer,
                        rec.get("reference_answer"),
                        rec.get("category", ""),
                    )
                    correctness = judgment.get("correctness", "partial")
                    rationale = judgment.get("rationale", "")
                else:
                    correctness = "partial"
                    rationale = "No judge key; skipping correctness grading"

            results.append(
                {
                    "id": rec["id"],
                    "category": rec.get("category"),
                    "query": rec["query"],
                    "answer": answer,
                    "guardrail_status": guardrail_status,
                    "citation_count": data.get("citation_count"),
                    "correctness": correctness,
                    "rationale": rationale,
                    "expected_behavior": expected_behavior,
                }
            )

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--groq-api-key", default=os.getenv("GROQ_API_KEY"))
    args = parser.parse_args()

    records = read_jsonl(args.dataset)
    results = evaluate_generation(args.api_url, records, args.groq_api_key)

    out_path = ROOT / "evals" / "results" / "generation_summary.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for r in results:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote generation results to {out_path}")

    # Simple aggregate stats
    total = len(results)
    correct = sum(r["correctness"] == "correct" for r in results)
    partial = sum(r["correctness"] == "partial" for r in results)
    incorrect = sum(r["correctness"] == "incorrect" for r in results)

    print(f"\nTotal: {total}")
    print(f"Correct: {correct} ({correct/total:.2%})")
    print(f"Partial: {partial} ({partial/total:.2%})")
    print(f"Incorrect: {incorrect} ({incorrect/total:.2%})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
