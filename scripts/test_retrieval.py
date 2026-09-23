import json
from typing import Any, Dict, List

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "jpm_governance_rag_v1"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_vec = model.encode([query])[0].tolist()

    client = QdrantClient(url=QDRANT_URL)

    # Use the newer query_points API
    result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=top_k,
    )

    # result.points is a list of ScoredPoint objects
    return [hit.payload for hit in result.points]


def main():
    q = input("Ask a question: ").strip()
    if not q:
        return

    hits = search(q, top_k=5)

    print("\n=== Top results ===")
    for i, p in enumerate(hits, start=1):
        print(f"\n[{i}]")
        print("doc_type:", p.get("doc_type"))
        print("doc_title:", p.get("doc_title"))
        print("section_path:", p.get("section_path"))
        print("item_number:", p.get("item_number"))
        print("page_pdf:", p.get("page_pdf"), "| page_printed:", p.get("page_printed"))
        print("content_type:", p.get("content_type"))
        print("text:", p.get("text", "")[:400], "...")


if __name__ == "__main__":
    main()