from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.qdrant_client import QdrantService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Initialize shared asynchronous resources once at startup.

    Later steps will add:
    - LangChain hybrid retrieval service;
    - Portkey gateway client;
    - Guardrails AI validators;
    - document ingestion components.
    """
    app.state.qdrant = QdrantService(settings)

    try:
        yield
    finally:
        await app.state.qdrant.close()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Async backend for a document-grounded corporate governance and "
        "enterprise-risk research assistant."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Groq-API-Key"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": (
            "JPMorgan Corporate Governance and Risk RAG API is running."
        )
    }


@app.get("/health")
async def health() -> dict:
    """
    Report application and vector database readiness.

    The endpoint returns HTTP 200 even if Qdrant is unavailable, so deployment
    systems can distinguish an API process that is alive from a dependency that
    is not yet connected. Later, Render can use a stricter readiness route.
    """
    qdrant_summary: dict

    try:
        qdrant_summary = await app.state.qdrant.get_health_summary()
    except Exception:
        qdrant_summary = {
            "connected": False,
            "collections": 0,
        }

    return {
        "status": "ok",
        "service": "jpmorgan-governance-risk-rag-api",
        "version": settings.app_version,
        "qdrant": qdrant_summary,
    }