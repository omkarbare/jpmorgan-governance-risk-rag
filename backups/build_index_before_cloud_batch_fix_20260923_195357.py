import json
import os
import re
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
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
    batch_size: int = 32,
) -> None:
    print("Converting chunks to Qdrant points (dense + sparse)...")

    points: list[PointStruct] = []

    for index, (chunk, dense_vector) in enumerate(
        zip(chunks, embeddings),
        start=1,
    ):
        page_content = chunk.get("page_content", "")
        metadata = chunk.get("metadata", {})

        sparse_vector = build_sparse_vector(page_content)

        points.append(
            PointStruct(
                id=index,
                vector={
                    "dense": dense_vector,
                    "text_bm25": sparse_vector,
                },
                payload={
                    "page_content": page_content,
                    "metadata": metadata,
                },
            )
        )

    total_batches = (len(points) + batch_size - 1) // batch_size

    print(
        f"Uploading {len(points)} points in {total_batches} batches "
        f"of up to {batch_size} points..."
    )

    for start in range(0, len(points), batch_size):
        batch_number = start // batch_size + 1
        batch = points[start:start + batch_size]

        for attempt in range(1, 4):
            try:
                client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=batch,
                    wait=True,
                )
                print(
                    f"Uploaded batch {batch_number}/{total_batches} "
                    f"({len(batch)} points)"
                )
                break
            except Exception as error:
                if attempt == 3:
                    raise RuntimeError(
                        f"Failed to upload batch {batch_number}/"
                        f"{total_batches} after 3 attempts."
                    ) from error

                sleep_seconds = attempt * 3
                print(
                    f"Batch {batch_number}/{total_batches} failed "
                    f"(attempt {attempt}/3): {error}. "
                    f"Retrying in {sleep_seconds} seconds..."
                )
                time.sleep(sleep_seconds)

    print("All points uploaded successfully.")

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