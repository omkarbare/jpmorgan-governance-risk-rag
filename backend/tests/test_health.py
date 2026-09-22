import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_without_qdrant() -> None:
    """
    The API health route remains available even if Qdrant is not running.

    Integration connectivity is tested separately once Docker Compose starts
    the Qdrant service.
    """
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ok"
    assert body["service"] == (
        "jpmorgan-governance-risk-rag-api"
    )
    assert "qdrant" in body
    assert "connected" in body["qdrant"]