from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector
from langsmith import traceable

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
SPARSE_VOCAB_PATH = DATA_DIR / "sparse_vocab.json"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "jpmorgan_governance_risk")

DENSE_TOP_K = 50
SPARSE_TOP_K = 50
FINAL_TOP_K = 5

STOPWORDS = {
    "the", "of", "and", "in", "to", "a", "for", "on", "with", "as",
    "is", "was", "are", "were", "be", "been", "being", "at", "by",
    "this", "that", "it", "from", "or", "an", "but", "which", "have",
    "has", "had", "not", "their", "they", "we", "you", "our", "its",
    "can", "will", "would", "could", "should", "may", "might", "must",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "only",
    "own", "same", "so", "than", "too", "very", "just", "also", "now",
}

# Global token → id mapping (loaded from file)
TOKEN_TO_ID: Dict[str, int] = {}


def load_sparse_vocab(path: Path):
    global TOKEN_TO_ID
    if not path.exists():
        raise FileNotFoundError(f"Sparse vocab not found at {path}")
    with path.open("r", encoding="utf-8") as f:
        TOKEN_TO_ID = json.load(f)


def tokenize_text(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if t not in STOPWORDS]


def build_sparse_vector_from_query(query: str) -> SparseVector:
    tokens = tokenize_text(query)
    counts = Counter(tokens)

    indices = []
    values = []

    for token, freq in counts.items():
        token_id = TOKEN_TO_ID.get(token)
        if token_id is None:
            continue
        indices.append(token_id)
        values.append(float(freq))

    return SparseVector(indices=indices, values=values)


def rrf_merge(
    dense_results: List[Tuple[str, float]],
    sparse_results: List[Tuple[str, float]],
    k: int = 60,
    top_k: int = FINAL_TOP_K,
) -> List[Tuple[str, float]]:
    """
    Reciprocal Rank Fusion (RRF) over two ranked lists.
    Each result is (point_id_str, score).
    Returns top_k fused results as (point_id_str, rrf_score).
    """
    scores: Dict[str, float] = {}

    for rank, (pid, _) in enumerate(dense_results, start=1):
        scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank)

    for rank, (pid, _) in enumerate(sparse_results, start=1):
        scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank)

    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_items[:top_k]


@traceable(run_type="retriever", name="hybrid_retriever")
def retrieve_documents(query: str, top_k: int = FINAL_TOP_K) -> List[Dict[str, Any]]:
    global TOKEN_TO_ID

    if not TOKEN_TO_ID:
        load_sparse_vocab(SPARSE_VOCAB_PATH)

    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
    )

    # 1. Dense search
    from langchain_community.embeddings import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    query_vec = embeddings.embed_query(query)

    dense_result = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vec,
        using="dense",
        limit=DENSE_TOP_K,
        with_payload=["page_content", "metadata"],
        with_vectors=False,
    )
    dense_results = dense_result.points

    # 2. Sparse (keyword/BM25-like) search
    sparse_vector = build_sparse_vector_from_query(query)

    sparse_result = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=sparse_vector,
        using="text_bm25",
        limit=SPARSE_TOP_K,
        with_payload=["page_content", "metadata"],
        with_vectors=False,
    )
    sparse_results = sparse_result.points

    # 3. RRF fusion
    dense_ranked = [(str(p.id), p.score) for p in dense_results]
    sparse_ranked = [(str(p.id), p.score) for p in sparse_results]

    fused = rrf_merge(dense_ranked, sparse_ranked, k=60, top_k=top_k)
    fused_ids = [pid for pid, _ in fused]

    # 4. Fetch full payloads for fused ids
    points = client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=[int(pid) for pid in fused_ids],
        with_payload=["page_content", "metadata"],
        with_vectors=False,
    )

    # Build result list in fused order
    id_to_point = {str(p.id): p for p in points}
    results = []
    for pid, rrf_score in fused:
        p = id_to_point.get(pid)
        if p is None:
            continue
        payload = p.payload
        results.append({
            "page_content": payload.get("page_content", ""),
            "metadata": payload.get("metadata", {}),
            "score": float(rrf_score),
        })

    return results