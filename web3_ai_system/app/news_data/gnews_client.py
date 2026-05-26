import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


DEFAULT_GNEWS_BASE_URL = "https://gnews.io/api/v4"
DEFAULT_TIMEOUT_SECONDS = 10.0


class GNewsClientError(RuntimeError):
    """Raised when GNews articles cannot be fetched."""


@dataclass(frozen=True)
class GNewsSettings:
    base_url: str
    api_key: str | None
    timeout_seconds: float


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_gnews_settings() -> GNewsSettings:
    _load_environment()
    return GNewsSettings(
        base_url=os.getenv("GNEWS_BASE_URL", DEFAULT_GNEWS_BASE_URL).rstrip("/"),
        api_key=os.getenv("GNEWS_API_KEY") or os.getenv("GNEWS_TOKEN"),
        timeout_seconds=float(os.getenv("NEWS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
    )


class GNewsClient:
    """Read-only client for GNews article search."""

    def __init__(self, settings: GNewsSettings | None = None) -> None:
        self.settings = settings or get_gnews_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.api_key)

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        if not self.settings.api_key:
            return []

        payload = self._get(
            "/search",
            {
                "apikey": self.settings.api_key,
                "q": query[:200],
                "lang": "en",
                "max": max(1, min(limit, 10)),
                "sortby": "publishedAt",
            },
        )
        rows = payload.get("articles")
        if not isinstance(rows, list):
            raise GNewsClientError("GNews returned an unexpected response format.")

        articles: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = row.get("title")
            if not title:
                continue
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            articles.append(
                {
                    "provider": "gnews",
                    "title": title,
                    "description": row.get("description"),
                    "snippet": row.get("content"),
                    "url": row.get("url"),
                    "published_at": row.get("publishedAt"),
                    "source": source.get("name") or source.get("url"),
                    "source_url": source.get("url"),
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
            raise GNewsClientError("GNews request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise GNewsClientError(f"GNews returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise GNewsClientError(f"Could not connect to GNews: {exc}") from exc
        except ValueError as exc:
            raise GNewsClientError("GNews returned invalid JSON.") from exc

