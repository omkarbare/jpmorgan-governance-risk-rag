from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the backend.

    Docker Compose will override QDRANT_URL inside the backend container.
    Local non-Docker execution defaults to localhost.
    """

    app_name: str = "JPMorgan Corporate Governance and Risk RAG API"
    app_version: str = "0.2.0"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "jpmorgan_governance_risk"

    allowed_origins: str = (
        "http://localhost:3000,"
        "http://localhost:3001"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object per running process."""
    return Settings()
