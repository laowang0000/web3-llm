import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.6:latest"


class OllamaClientError(RuntimeError):
    """Raised when the local Ollama service cannot complete a request."""


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str
    model: str
    timeout_seconds: float = 60.0
    num_predict: int | None = None
    think: bool = False


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_ollama_settings() -> OllamaSettings:
    _load_environment()
    return OllamaSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/"),
        model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
        num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "0")) or None,
        think=os.getenv("OLLAMA_THINK", "false").strip().lower() in {"1", "true", "yes"},
    )


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
