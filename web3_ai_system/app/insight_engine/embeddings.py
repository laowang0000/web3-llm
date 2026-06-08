import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_EMBED_MODEL = "nomic-embed-text"


class EmbeddingClientError(RuntimeError):
    """Raised when embeddings cannot be generated."""


@dataclass(frozen=True)
class EmbeddingSettings:
    provider: str
    model: str
    base_url: str
    timeout_seconds: float
    batch_size: int = 8


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_embedding_settings(model_name: str | None = None) -> EmbeddingSettings:
    _load_environment()
    provider = os.getenv("EMBEDDING_PROVIDER", "ollama").strip().lower()
    default_model = os.getenv("OLLAMA_EMBED_MODEL", DEFAULT_OLLAMA_EMBED_MODEL)
    if provider == "openai":
        default_model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    return EmbeddingSettings(
        provider=provider,
        model=model_name or default_model,
        base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/"),
        timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
        batch_size=max(1, int(os.getenv("OLLAMA_EMBED_BATCH_SIZE", "8"))),
    )


class OllamaEmbeddings(Embeddings):
    """LangChain-compatible embeddings backed by local Ollama."""

    def __init__(self, settings: EmbeddingSettings | None = None) -> None:
        self.settings = settings or get_embedding_settings()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.settings.batch_size):
            batch = texts[start : start + self.settings.batch_size]
            embeddings.extend(self._embed_batch(batch))
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.settings.model, "input": texts}
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.post(f"{self.settings.base_url}/api/embed", json=payload)
                if response.status_code == 404:
                    return [self._embed_single_legacy(client, text) for text in texts]
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise EmbeddingClientError("Ollama embedding request timed out.") from exc
        except httpx.RequestError as exc:
            raise EmbeddingClientError(f"Could not connect to Ollama embeddings: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise EmbeddingClientError(f"Ollama embeddings returned HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except ValueError as exc:
            raise EmbeddingClientError("Ollama embeddings returned invalid JSON.") from exc

        embeddings = data.get("embeddings")
        if not embeddings:
            raise EmbeddingClientError("Ollama response did not contain embeddings.")
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def _embed_single_legacy(self, client: httpx.Client, text: str) -> list[float]:
        response = client.post(
            f"{self.settings.base_url}/api/embeddings",
            json={"model": self.settings.model, "prompt": text},
        )
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        if not embedding:
            raise EmbeddingClientError("Ollama legacy embedding response did not contain embedding.")
        return embedding


def build_embeddings(model_name: str | None = None) -> Any:
    settings = get_embedding_settings(model_name)
    if settings.provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=settings.model)
    if settings.provider != "ollama":
        raise EmbeddingClientError(f"Unsupported embedding provider: {settings.provider}")
    return OllamaEmbeddings(settings=settings)
