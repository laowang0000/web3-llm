import os
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:9b"
DEFAULT_OLLAMA_EMBED_MODEL = "nomic-embed-text"
EXCLUDED_CHAT_MODEL_NAMES = {"nomic-embed-text", "nomic-embed-text:latest", "deepseek-ocr:latest"}
EXCLUDED_CHAT_MODEL_KEYWORDS = ("embed", "embedding", "ocr")


class OllamaClientError(RuntimeError):
    """Raised when the local Ollama service cannot complete a request."""


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str
    model: str
    timeout_seconds: float = 60.0
    num_predict: int | None = None
    think: bool = False

    def with_model(self, model: str) -> "OllamaSettings":
        return replace(self, model=model)

    def with_base_url(self, base_url: str) -> "OllamaSettings":
        return replace(self, base_url=normalize_base_url(base_url))


@dataclass(frozen=True)
class OpenAICompatibleSettings:
    base_url: str
    model: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 60.0

    def with_model(self, model: str) -> "OpenAICompatibleSettings":
        return replace(self, model=model)


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_ollama_settings() -> OllamaSettings:
    _load_environment()
    return OllamaSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/"),
        model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        timeout_seconds=float(os.getenv("OLLAMA_CHAT_TIMEOUT_SECONDS") or os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
        num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "160")) or None,
        think=os.getenv("OLLAMA_THINK", "false").strip().lower() in {"1", "true", "yes"},
    )


def normalize_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        raise ValueError("Model provider base URL is required.")
    if not normalized.startswith(("http://", "https://")):
        raise ValueError("Model provider base URL must start with http:// or https://.")
    return normalized


def get_embedding_model_name() -> str:
    _load_environment()
    return os.getenv("OLLAMA_EMBED_MODEL", DEFAULT_OLLAMA_EMBED_MODEL)


def is_selectable_chat_model(model_name: str) -> bool:
    normalized = (model_name or "").strip().lower()
    if not normalized:
        return False
    if normalized in EXCLUDED_CHAT_MODEL_NAMES:
        return False
    return not any(keyword in normalized for keyword in EXCLUDED_CHAT_MODEL_KEYWORDS)


class OllamaChatClient:
    """Small, frontend-safe wrapper around Ollama's local chat API."""

    def __init__(self, settings: OllamaSettings | None = None) -> None:
        self.settings = settings or get_ollama_settings()

    def health(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.settings.base_url}/api/tags")
                response.raise_for_status()
                payload = response.json()
        except httpx.RequestError as exc:
            return {
                "reachable": False,
                "base_url": self.settings.base_url,
                "model": self.settings.model,
                "message": f"Ollama is not reachable: {exc}",
            }
        except httpx.HTTPStatusError as exc:
            return {
                "reachable": False,
                "base_url": self.settings.base_url,
                "model": self.settings.model,
                "message": f"Ollama returned HTTP {exc.response.status_code}",
            }

        models = [item.get("name") for item in payload.get("models", []) if item.get("name")]
        return {
            "reachable": True,
            "base_url": self.settings.base_url,
            "model": self.settings.model,
            "model_available": self.settings.model in models,
            "available_models": models,
        }

    def list_models(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.settings.base_url}/api/tags")
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise OllamaClientError("Ollama model listing timed out. Is Ollama running locally?") from exc
        except httpx.RequestError as exc:
            raise OllamaClientError(
                f"Could not connect to Ollama at {self.settings.base_url}. Is Ollama running?"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaClientError(f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except ValueError as exc:
            raise OllamaClientError("Ollama returned an invalid JSON response while listing models.") from exc

        local_models = [item.get("name") for item in payload.get("models", []) if item.get("name")]
        chat_models = [name for name in local_models if is_selectable_chat_model(name)]
        return {
            "base_url": self.settings.base_url,
            "default_chat_model": self.settings.model,
            "current_chat_model": self.settings.model,
            "embedding_model": get_embedding_model_name(),
            "local_models": local_models,
            "chat_models": chat_models,
            "excluded_models": [name for name in local_models if name not in chat_models],
        }

    def with_model(self, model: str) -> "OllamaChatClient":
        return OllamaChatClient(settings=self.settings.with_model(model))

    def with_base_url(self, base_url: str) -> "OllamaChatClient":
        return OllamaChatClient(settings=self.settings.with_base_url(base_url))

    def chat(
        self,
        message: str,
        system_prompt: str | None = None,
        context: str | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context:
            messages.append({"role": "system", "content": f"Context:\n{context}"})
        messages.append({"role": "user", "content": message})

        payload = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
            "think": self.settings.think,
        }
        if self.settings.num_predict:
            payload["options"] = {"num_predict": self.settings.num_predict}

        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.post(f"{self.settings.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise OllamaClientError("Ollama request timed out. Try a smaller prompt or a faster local model.") from exc
        except httpx.RequestError as exc:
            raise OllamaClientError(
                f"Could not connect to Ollama at {self.settings.base_url}. Is Ollama running?"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaClientError(f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except ValueError as exc:
            raise OllamaClientError("Ollama returned an invalid JSON response.") from exc

        content = data.get("message", {}).get("content")
        if not content:
            raise OllamaClientError("Ollama response did not contain message.content.")
        return str(content).strip()


class OpenAICompatibleChatClient:
    """Minimal OpenAI-compatible chat client for remote API endpoints."""

    def __init__(self, settings: OpenAICompatibleSettings) -> None:
        self.settings = settings

    def with_model(self, model: str) -> "OpenAICompatibleChatClient":
        return OpenAICompatibleChatClient(settings=self.settings.with_model(model))

    def list_models(self) -> dict[str, Any]:
        headers = self._headers()
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.settings.base_url}/models", headers=headers)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise OllamaClientError("OpenAI-compatible model listing timed out.") from exc
        except httpx.RequestError as exc:
            raise OllamaClientError("Could not connect to the OpenAI-compatible API endpoint.") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaClientError(f"OpenAI-compatible endpoint returned HTTP {exc.response.status_code}.") from exc
        except ValueError as exc:
            raise OllamaClientError("OpenAI-compatible endpoint returned an invalid JSON response.") from exc

        models = []
        for item in payload.get("data", []):
            model_id = item.get("id") if isinstance(item, dict) else None
            if model_id:
                models.append(model_id)
        return {
            "base_url": self.settings.base_url,
            "provider_type": "openai_compatible",
            "model_name": self.settings.model,
            "available_models": models,
            "model_available": self.settings.model in models if models else None,
        }

    def chat(
        self,
        message: str,
        system_prompt: str | None = None,
        context: str | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context:
            messages.append({"role": "system", "content": f"Context:\n{context}"})
        messages.append({"role": "user", "content": message})

        payload = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.post(f"{self.settings.base_url}/chat/completions", headers=self._headers(), json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise OllamaClientError("OpenAI-compatible chat request timed out.") from exc
        except httpx.RequestError as exc:
            raise OllamaClientError("Could not connect to the OpenAI-compatible API endpoint.") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaClientError(f"OpenAI-compatible endpoint returned HTTP {exc.response.status_code}.") from exc
        except ValueError as exc:
            raise OllamaClientError("OpenAI-compatible endpoint returned an invalid JSON response.") from exc

        choices = data.get("choices") or []
        if not choices:
            raise OllamaClientError("OpenAI-compatible response did not contain choices.")
        first_choice = choices[0] or {}
        content = (first_choice.get("message") or {}).get("content") or first_choice.get("text")
        if not content:
            raise OllamaClientError("OpenAI-compatible response did not contain message content.")
        return str(content).strip()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        return headers
