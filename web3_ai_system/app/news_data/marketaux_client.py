import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


DEFAULT_MARKETAUX_BASE_URL = "https://api.marketaux.com/v1"
DEFAULT_TIMEOUT_SECONDS = 10.0


class MarketauxClientError(RuntimeError):
    """Raised when Marketaux news cannot be fetched."""


@dataclass(frozen=True)
class MarketauxSettings:
    base_url: str
    api_token: str | None
    timeout_seconds: float


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_marketaux_settings() -> MarketauxSettings:
    _load_environment()
    return MarketauxSettings(
        base_url=os.getenv("MARKETAUX_BASE_URL", DEFAULT_MARKETAUX_BASE_URL).rstrip("/"),
        api_token=os.getenv("MARKETAUX_API_TOKEN") or os.getenv("MARKETAUX_TOKEN"),
        timeout_seconds=float(os.getenv("NEWS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
    )


class MarketauxClient:
    """Read-only client for Marketaux financial news."""

    def __init__(self, settings: MarketauxSettings | None = None) -> None:
        self.settings = settings or get_marketaux_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.api_token)

    def fetch_news(self, search_query: str, limit: int = 3) -> list[dict[str, Any]]:
        if not self.settings.api_token:
            return []

        payload = self._get(
            "/news/all",
            {
                "api_token": self.settings.api_token,
                "search": search_query,
                "language": "en",
                "limit": max(1, min(limit, 10)),
                "group_similar": "true",
            },
        )
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise MarketauxClientError("Marketaux returned an unexpected response format.")

        articles: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = row.get("title")
            if not title:
                continue
            articles.append(
                {
                    "provider": "marketaux",
                    "title": title,
                    "description": row.get("description"),
                    "snippet": row.get("snippet"),
                    "url": row.get("url"),
                    "published_at": row.get("published_at"),
                    "source": row.get("source"),
                    "entities": self._entity_summaries(row.get("entities")),
                }
            )
        return articles

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.settings.base_url}{path}"
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise MarketauxClientError("Marketaux request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise MarketauxClientError(f"Marketaux returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise MarketauxClientError(f"Could not connect to Marketaux: {exc}") from exc
        except ValueError as exc:
            raise MarketauxClientError("Marketaux returned invalid JSON.") from exc

    def _entity_summaries(self, entities: Any) -> list[dict[str, Any]]:
        if not isinstance(entities, list):
            return []

        summaries: list[dict[str, Any]] = []
        for entity in entities[:5]:
            if not isinstance(entity, dict):
                continue
            summaries.append(
                {
                    "symbol": entity.get("symbol"),
                    "name": entity.get("name"),
                    "type": entity.get("type"),
                    "sentiment_score": entity.get("sentiment_score"),
                    "match_score": entity.get("match_score"),
                }
            )
        return summaries

