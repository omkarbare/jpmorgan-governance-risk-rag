import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseVector,
)

ROOT = Path(__file__).resolve().parents[1]
PARSED_DIR = ROOT / "data" / "parsed"
DATA_DIR = ROOT / "data"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "jpmorgan_governance_risk")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

SPARSE_VOCAB_PATH = DATA_DIR / "sparse_vocab.json"

# Global token → id mapping for sparse vectors
GLOBAL_TOKEN_TO_ID: Dict[str, int] = {}
GLOBAL_NEXT_TOKEN_ID = 0


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


def tokenize_text(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if t not in STOPWORDS]


def update_vocab_for_text(text: str):
    global GLOBAL_NEXT_TOKEN_ID
    tokens = set(tokenize_text(text))
    for t in tokens:
        if t not in GLOBAL_TOKEN_TO_ID:
            GLOBAL_TOKEN_TO_ID[t] = GLOBAL_NEXT_TOKEN_ID
            GLOBAL_NEXT_TOKEN_ID += 1


def build_final_sparse_vector(text: str) -> Dict[str, List]:
    """
    Return sparse vector as a plain dict with 'indices' and 'values'.
    This avoids Pydantic issues when embedding into the larger payload.
    """
    tokens = tokenize_text(text)
    counts = Counter(tokens)

    indices = []
    values = []

    for token, freq in counts.items():
        token_id = GLOBAL_TOKEN_TO_ID.get(token)
        if token_id is None:
            continue
        indices.append(token_id)
        values.append(float(freq))

    return {"indices": indices, "values": values}


def save_sparse_vocab(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(GLOBAL_TOKEN_TO_ID, f, ensure_ascii=False, indent=2)


def load_chunks() -> List[Dict[str, Any]]:
    chunks = []
    if not PARSED_DIR.exists():
        return chunks
    for path in sorted(PARSED_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                chunks.append(rec)
    return chunks


def prepare_text_for_embedding(rec: Dict[str, Any]) -> str:
    meta = rec["metadata"]
    prefix = (
        f"[{meta['doc_type']}] "
        f"{meta.get('doc_title', '')} | "
        f"{meta.get('section_path', '')} | "
    )
    text = rec.get("text", "")
    return prefix + text


def build_embeddings(
    chunks: List[Dict[str, Any]],
    model: SentenceTransformer,
    batch_size: int = 32,
) -> np.ndarray:
    texts = [prepare_text_for_embedding(c) for c in chunks]
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    return embeddings


def create_or_recreate_collection(client: QdrantClient, dim: int):
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if COLLECTION_NAME in names:
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(size=dim, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "text_bm25": SparseVectorParams(),
        },
    )


def upsert_chunks_with_sparse(
    client: QdrantClient,
    chunks: List[Dict[str, Any]],
    embeddings: np.ndarray,
    batch_size: int = 32,
    max_retries: int = 3,
):
    """
    Upload dense and sparse vectors in small batches suitable for Qdrant Cloud.
    Each point retains page content and all citation metadata in its payload.
    """
    total = len(chunks)
    total_batches = (total + batch_size - 1) // batch_size

    print(
        f"Uploading {total} points in {total_batches} batches "
        f"of up to {batch_size} points..."
    )

    for offset in range(0, total, batch_size):
        batch_number = offset // batch_size + 1
        batch_chunks = chunks[offset : offset + batch_size]
        batch_embs = embeddings[offset : offset + batch_size]

        points = []

        for i, (chunk, emb) in enumerate(zip(batch_chunks, batch_embs)):
            meta = chunk["metadata"]
            text = chunk.get("text", "")

            payload = {
                "page_content": text,
                "metadata": {
                    "chunk_id": meta.get("chunk_id", ""),
                    "doc_id": meta.get("doc_id", ""),
                    "doc_title": meta.get("doc_title", ""),
                    "doc_type": meta.get("doc_type", ""),
                    "doc_year": meta.get("doc_year"),
                    "source_file": meta.get("source_file", ""),
                    "source_url": meta.get("source_url", ""),
                    "page_pdf": meta.get("page_pdf"),
                    "page_printed": meta.get("page_printed"),
                    "section_path": meta.get("section_path", ""),
                    "section_title": meta.get("section_title", ""),
                    "item_number": meta.get("item_number", ""),
                    "content_type": meta.get("content_type", "text"),
                    "table_caption": meta.get("table_caption"),
                    "table_id": meta.get("table_id"),
                    "parent_id": meta.get("parent_id"),
                    "text_hash": meta.get("text_hash", ""),
                    "ingestion_date": meta.get("ingestion_date", ""),
                    "parser_version": meta.get("parser_version", ""),
                    "effective_date": meta.get("effective_date"),
                    "status": meta.get("status", "current"),
                    "access_level": meta.get("access_level", "public"),
                },
            }

            points.append(
                {
                    "id": offset + i + 1,
                    "vector": {
                        "dense": emb.tolist(),
                        "text_bm25": build_final_sparse_vector(text),
                    },
                    "payload": payload,
                }
            )

        for attempt in range(1, max_retries + 1):
            try:
                client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points,
                    wait=False,
                )

                print(
                    f"  Uploaded batch {batch_number}/{total_batches} "
                    f"({len(points)} points)"
                )
                break

            except Exception as error:
                if attempt == max_retries:
                    raise RuntimeError(
                        f"Failed to upload batch {batch_number}/{total_batches} "
                        f"after {max_retries} attempts."
                    ) from error

                sleep_seconds = attempt * 5

                print(
                    f"  Batch {batch_number}/{total_batches} failed "
                    f"(attempt {attempt}/{max_retries}): {error}"
                )
                print(f"  Retrying in {sleep_seconds} seconds...")

                time.sleep(sleep_seconds)

    print("Waiting for Qdrant to finalize collection updates...")

    client.count(
        collection_name=COLLECTION_NAME,
        exact=False,
        wait=True,
    )

    print("All point batches uploaded successfully.")

def main():
    global GLOBAL_TOKEN_TO_ID, GLOBAL_NEXT_TOKEN_ID

    print("Loading chunks...")
    chunks = load_chunks()
    if not chunks:
        print("No chunks found in", PARSED_DIR)
        return

    print(f"Loaded {len(chunks)} chunks")

    # Pass 1: build vocab for sparse vectors
    print("Building token vocabulary for sparse vectors...")
    for chunk in chunks:
        text = chunk.get("text", "")
        update_vocab_for_text(text)

    print(f"Vocabulary size: {len(GLOBAL_TOKEN_TO_ID)} tokens")

    # Save vocab for retrieval to reuse
    save_sparse_vocab(SPARSE_VOCAB_PATH)
    print(f"Saved sparse vocab to {SPARSE_VOCAB_PATH}")

    print("Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Computing dense embeddings...")
    embeddings = build_embeddings(chunks, model)
    dim = embeddings.shape[1]

    print("Connecting to Qdrant...")
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=180,
    )

    print(f"Creating/recreating collection: {COLLECTION_NAME}")
    create_or_recreate_collection(client, dim)

    print("Converting chunks to Qdrant points (dense + sparse) and upserting...")
    upsert_chunks_with_sparse(client, chunks, embeddings)

    print("Done.")


if __name__ == "__main__":
    main()