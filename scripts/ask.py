import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

# Import our production LLM client
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.llm_client import chat_completion

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "jpmorgan_governance_risk")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def retrieve_chunks(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_vec = model.encode([query])[0].tolist()

    qdrant = QdrantClient(url=QDRANT_URL)

    result = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=top_k,
    )

    return [hit.payload for hit in result.points]


def build_citation_header(i: int, p: Dict[str, Any]) -> str:
    doc_type = p.get("doc_type", "")
    doc_title = p.get("doc_title", "")
    section_path = p.get("section_path", "")
    item_number = p.get("item_number", "")
    page_pdf = p.get("page_pdf")
    page_printed = p.get("page_printed")

    parts = []
    if doc_type:
        parts.append(doc_type)
    if doc_title:
        parts.append(doc_title)
    if section_path:
        parts.append(section_path)
    if item_number:
        parts.append(item_number)
    if page_printed:
        parts.append(f"page {page_printed}")
    elif page_pdf:
        parts.append(f"page {page_pdf}")

    meta_str = " | ".join(parts)
    return f"[{i}] {meta_str}"


def build_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
    lines = [
        "You are a precise assistant for J.P. Morgan governance and risk documents.",
        "Use ONLY the retrieved chunks below to answer the question.",
        "Cite your sources using numbered references like [1], [2], etc.",
        "Each number must correspond exactly to one of the retrieved chunks.",
        "Do NOT invent page numbers, sections, or documents.",
        "",
        "Question:",
        query,
        "",
        "Retrieved chunks:",
    ]

    for i, c in enumerate(chunks, start=1):
        header = build_citation_header(i, c)
        text = c.get("text", "")
        lines.append(f"\n{header}")
        lines.append(text)

    lines.append("")
    lines.append(
        "Answer the question in 3–6 sentences. "
        "Where relevant, include citations like [1], [2]. "
        "Only use numbers that appear in the retrieved chunks."
    )

    return "\n".join(lines)


def ask(query: str, top_k: int = 5) -> Tuple[str, List[Dict[str, Any]]]:
    chunks = retrieve_chunks(query, top_k=top_k)
    if not chunks:
        return "No relevant documents found.", []

    prompt = build_prompt(query, chunks)
    messages = [{"role": "user", "content": prompt}]

    answer = chat_completion(messages, temperature=0.2, max_tokens=512)

    return answer, chunks


def main():
    print("Ask a question about J.P. Morgan governance/risk documents:")
    q = input("> ").strip()
    if not q:
        return

    answer, chunks = ask(q, top_k=5)

    print("\n=== Answer ===")
    print(answer)

    print("\n=== Citations ===")
    for i, c in enumerate(chunks, start=1):
        header = build_citation_header(i, c)
        print(f"[{i}] {header}")


if __name__ == "__main__":
    main()