from __future__ import annotations

from qdrant_client import AsyncQdrantClient

from app.config import Settings


class QdrantService:
    """
    Owns the asynchronous Qdrant client.

    Later steps will create collections, ingest citation-aware chunks, and run
    hybrid retrieval. For now, this service only checks connectivity and counts
    collections.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=10,
        )

    async def get_health_summary(self) -> dict[str, int | bool]:
        """
        Verify Qdrant connectivity by listing collections.
        """
        collections = await self.client.get_collections()

        return {
            "connected": True,
            "collections": len(collections.collections),
        }

    async def close(self) -> None:
        """Close the underlying async HTTP client cleanly."""
        await self.client.close()