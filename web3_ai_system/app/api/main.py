import os
import re
import sqlite3
from typing import Any

import httpx
from fastapi import FastAPI, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.analysis.hybrid_service import HybridAnalysisService, HybridAnalysisServiceError
from app.config import settings
from app.defi_data.defillama_client import defillama_context_enabled
from app.insight_engine.embeddings import get_embedding_settings
from app.llm.ollama_client import (
    OllamaChatClient,
    OllamaClientError,
    get_embedding_model_name,
    OpenAICompatibleChatClient,
    OpenAICompatibleSettings,
    ResearchApiChatClient,
    ResearchApiSettings,
    is_selectable_chat_model,
    normalize_base_url,
)
from app.market_data.service import MarketDataService, MarketDataServiceError, get_provider_order
from app.news_data.service import LiveNewsService
from app.prediction_engine.service import PredictionService, PredictionServiceError

SUPPORTED_SYMBOL_ALIASES = {
    "BTCUSDT": ("BTC", "BTCUSDT", "Bitcoin"),
    "ETHUSDT": ("ETH", "ETHUSDT", "Ethereum"),
    "SOLUSDT": ("SOL", "SOLUSDT", "Solana"),
    "BNBUSDT": ("BNB", "BNBUSDT", "Binance Coin"),
    "XRPUSDT": ("XRP", "XRPUSDT", "Ripple"),
    "ADAUSDT": ("ADA", "ADAUSDT", "Cardano"),
    "DOGEUSDT": ("DOGE", "DOGEUSDT", "Dogecoin"),
    "MATICUSDT": ("MATIC", "MATICUSDT", "Polygon"),
    "POLUSDT": ("POL", "POLUSDT"),
    "AVAXUSDT": ("AVAX", "AVAXUSDT", "Avalanche"),
    "DOTUSDT": ("DOT", "DOTUSDT", "Polkadot"),
}

COMPARISON_KEYWORDS = (
    "compare",
    "versus",
    "vs",
    "against",
    "correlation",
    "relationship",
    "stronger than",
    "weaker than",
    "eth and btc",
    "btc and eth",
)


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: ApiError | None = None
    sources: list[str] = Field(default_factory=list)


class ModelProviderConfig(BaseModel):
    provider_type: str = Field(
        default="local_ollama",
        description="Model provider: local_ollama, remote_ollama, openai_compatible, research_api, or custom_endpoint.",
    )
    base_url: str | None = Field(default=None, description="Remote provider base URL or endpoint URL.")
    api_key: str | None = Field(default=None, description="API key for OpenAI-compatible or Research API providers.")
    model_name: str | None = Field(default=None, description="Provider model name for this request.")

    def normalized_type(self) -> str:
        return (self.provider_type or "local_ollama").strip().lower()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question or instruction.")
    system_prompt: str | None = Field(
        default="You are a cryptocurrency market insight assistant. Explain clearly and avoid financial advice.",
        description="Optional system instruction for Ollama.",
    )
    context: str | None = Field(default=None, description="Optional retrieved context for prompt augmentation.")
    sources: list[str] = Field(default_factory=list, description="Optional source labels associated with context.")
    selected_model: str | None = Field(default=None, min_length=1, description="Optional Ollama chat model for this request.")
    model: str | None = Field(default=None, min_length=1, description="Alias for selected_model used by simple clients.")
    provider_config: ModelProviderConfig | None = Field(default=None, description="Optional model provider for this request.")

    def resolved_selected_model(self) -> str | None:
        return _resolve_selected_model(self.selected_model, self.model)


class BasicAnalysisRequest(BaseModel):
    symbol: str = Field(..., min_length=2, description="Trading pair such as BTCUSDT, ETHUSDT, or SOLUSDT.")
    timeframe: str = Field(default="1h", description="Binance candle interval such as 15m, 1h, 4h, or 1d.")
    limit: int = Field(default=120, ge=50, le=1000, description="Number of candles to fetch.")


class HybridAnalysisRequest(BasicAnalysisRequest):
    question: str | None = Field(default=None, min_length=1, description="User question for the hybrid market analysis.")
    query: str | None = Field(default=None, min_length=1, description="Alias for question used by simple clients.")
    selected_model: str | None = Field(default=None, min_length=1, description="Optional Ollama chat model for this request.")
    model: str | None = Field(default=None, min_length=1, description="Alias for selected_model used by simple clients.")
    provider_config: ModelProviderConfig | None = Field(default=None, description="Optional model provider for this request.")

    def resolved_question(self) -> str:
        question = (self.question or self.query or "").strip()
        if not question:
            raise ValueError("Either question or query is required for hybrid analysis.")
        return question

    def resolved_selected_model(self) -> str | None:
        return _resolve_selected_model(self.selected_model, self.model)


class PredictionRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", min_length=2, description="Trading pair such as BTCUSDT.")
    timeframe: str = Field(default="1d", description="Binance candle interval such as 1h, 4h, or 1d.")
    horizon_candles: int | None = Field(default=None, ge=1, le=30, description="Forward trend horizon in future candles.")
    horizon_days: int | None = Field(default=None, ge=1, le=30, description="Backward-compatible alias for horizon_candles.")
    limit: int = Field(default=300, ge=120, le=1000, description="Number of candles for training and backtest.")

    def resolved_horizon_candles(self) -> int:
        return int(self.horizon_candles or self.horizon_days or 3)


class TestModelConnectionRequest(BaseModel):
    provider_config: ModelProviderConfig = Field(..., description="Provider connection settings to test.")


def _response_content(response: ApiResponse) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return response.dict()


def _status_item(
    name: str,
    status_value: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status_value,
        "ok": status_value == "ok",
        "message": message,
        "details": details or {},
    }


def _rag_collection_name(provider: str, model: str) -> str:
    safe_model = "".join(character if character.isalnum() else "_" for character in model.lower())
    return f"crypto_insight_{provider}_{safe_model}"[:63]


def _count_rag_embeddings(collection_name: str) -> int:
    sqlite_path = settings.chroma_persist_dir / "chroma.sqlite3"
    if not sqlite_path.exists():
        return 0

    with sqlite3.connect(sqlite_path) as connection:
        cursor = connection.cursor()
        row = cursor.execute(
            "select id from collections where name = ?",
            (collection_name,),
        ).fetchone()
        if row is None:
            return 0

        collection_id = row[0]
        segment_rows = cursor.execute(
            "select id from segments where collection = ?",
            (collection_id,),
        ).fetchall()
        segment_ids = [segment_row[0] for segment_row in segment_rows]
        if not segment_ids:
            return 0

        placeholders = ",".join("?" for _ in segment_ids)
        count = cursor.execute(
            f"select count(*) from embeddings where segment_id in ({placeholders})",
            segment_ids,
        ).fetchone()[0]
        return int(count or 0)


def _rag_index_status() -> dict[str, Any]:
    embedding_settings = get_embedding_settings()
    collection_name = _rag_collection_name(embedding_settings.provider, embedding_settings.model)
    try:
        count = _count_rag_embeddings(collection_name)
    except sqlite3.Error as exc:
        return _status_item(
            "RAG / Chroma index",
            "error",
            f"Chroma index could not be inspected: {exc}",
            details={"collection": collection_name, "path": str(settings.chroma_persist_dir)},
        )

    if count <= 0:
        return _status_item(
            "RAG / Chroma index",
            "warning",
            "No indexed chunks found. Run python -m app.scripts.index_rag before RAG questions.",
            details={"collection": collection_name, "path": str(settings.chroma_persist_dir), "indexed_chunks": count},
        )

    return _status_item(
        "RAG / Chroma index",
        "ok",
        f"Indexed context is available ({count} chunks).",
        details={"collection": collection_name, "path": str(settings.chroma_persist_dir), "indexed_chunks": count},
    )


def _news_provider_status() -> dict[str, Any]:
    service = LiveNewsService()
    providers = {
        "marketaux": service.marketaux.is_configured,
        "gnews": service.gnews.is_configured,
    }
    configured = [name for name, is_configured in providers.items() if is_configured]
    if configured:
        return _status_item(
            "News providers",
            "ok",
            f"Configured providers: {', '.join(configured)}.",
            details={"providers": providers, "max_articles": service.max_articles},
        )
    return _status_item(
        "News providers",
        "warning",
        "No Marketaux or GNews API key is configured. News questions will continue without live news context.",
        details={"providers": providers, "max_articles": service.max_articles},
    )


def _defillama_status() -> dict[str, Any]:
    enabled = defillama_context_enabled()
    return _status_item(
        "DeFiLlama context",
        "ok" if enabled else "warning",
        "DeFiLlama context is enabled." if enabled else "DeFiLlama context is disabled by ENABLE_DEFILLAMA_CONTEXT.",
        details={"enabled": enabled},
    )


def _market_provider_status() -> dict[str, Any]:
    provider_order = get_provider_order()
    if provider_order:
        return _status_item(
            "Market data providers",
            "ok",
            f"Provider order configured: {', '.join(provider_order)}.",
            details={"provider_order": provider_order},
        )
    return _status_item(
        "Market data providers",
        "error",
        "No supported market provider is configured.",
        details={"provider_order": provider_order},
    )


def _ollama_generation_status(client: OllamaChatClient) -> dict[str, Any]:
    probe_timeout = min(
        client.settings.timeout_seconds,
        float(os.getenv("OLLAMA_STATUS_PROBE_TIMEOUT_SECONDS", "12")),
    )
    payload = {
        "model": client.settings.model,
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "stream": False,
        "think": client.settings.think,
        "options": {"num_predict": 8},
    }
    try:
        with httpx.Client(timeout=probe_timeout) as http_client:
            response = http_client.post(f"{client.settings.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException:
        return _status_item(
            "Ollama generation",
            "error",
            f"Ollama chat generation timed out during a {probe_timeout:g}s probe. /analyze will use structured fallback if this persists.",
            details={
                "model": client.settings.model,
                "probe_timeout_seconds": probe_timeout,
                "configured_timeout_seconds": client.settings.timeout_seconds,
            },
        )
    except httpx.HTTPStatusError as exc:
        return _status_item(
            "Ollama generation",
            "error",
            f"Ollama generation returned HTTP {exc.response.status_code}.",
            details={"model": client.settings.model, "probe_timeout_seconds": probe_timeout},
        )
    except (httpx.RequestError, ValueError) as exc:
        return _status_item(
            "Ollama generation",
            "error",
            f"Ollama generation probe failed: {exc}",
            details={"model": client.settings.model, "probe_timeout_seconds": probe_timeout},
        )

    content = str((data.get("message") or {}).get("content") or "").strip()
    if not content:
        return _status_item(
            "Ollama generation",
            "error",
            "Ollama generation returned no message content.",
            details={"model": client.settings.model, "probe_timeout_seconds": probe_timeout},
        )

    prompt_eval_count = int(data.get("prompt_eval_count") or 0)
    prompt_eval_seconds = float(data.get("prompt_eval_duration") or 0) / 1_000_000_000
    total_seconds = float(data.get("total_duration") or 0) / 1_000_000_000
    seconds_per_prompt_token = prompt_eval_seconds / prompt_eval_count if prompt_eval_count else None
    details = {
        "model": client.settings.model,
        "probe_timeout_seconds": probe_timeout,
        "configured_timeout_seconds": client.settings.timeout_seconds,
        "probe_total_seconds": round(total_seconds, 2) if total_seconds else None,
        "prompt_eval_count": prompt_eval_count,
        "prompt_eval_seconds": round(prompt_eval_seconds, 2) if prompt_eval_seconds else None,
        "seconds_per_prompt_token": round(seconds_per_prompt_token, 3) if seconds_per_prompt_token else None,
    }
    if seconds_per_prompt_token and seconds_per_prompt_token > 0.25:
        return _status_item(
            "Ollama generation",
            "warning",
            "Short generation works, but prompt evaluation is slow. Larger /analyze prompts may timeout and use structured fallback.",
            details=details,
        )

    return _status_item(
        "Ollama generation",
        "ok",
        "Ollama completed a short chat generation probe.",
        details=details,
    )


def _is_market_input_error(exc: Exception) -> bool:
    message = str(exc)
    return message.startswith("Unsupported market symbol") or message.startswith("Symbol is required")


def _market_error_status(exc: Exception) -> int:
    if _is_market_input_error(exc):
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_502_BAD_GATEWAY


def _market_error_code(default_code: str, exc: Exception) -> str:
    if _is_market_input_error(exc):
        return "INVALID_MARKET_SYMBOL"
    return default_code


def _resolve_selected_model(selected_model: str | None, model: str | None) -> str | None:
    candidate = (selected_model or model or "").strip()
    if not candidate:
        return None
    if not is_selectable_chat_model(candidate):
        raise ValueError(f"Model is not selectable for chat generation: {candidate}")
    return candidate


def _provider_type(provider_config: ModelProviderConfig | None) -> str:
    if provider_config is None:
        return "local_ollama"
    return provider_config.normalized_type()


def _resolve_model_client(provider_config: ModelProviderConfig | None, selected_model: str | None = None) -> Any:
    provider_type = _provider_type(provider_config)
    if provider_type == "local_ollama":
        client = OllamaChatClient()
        if selected_model:
            client = client.with_model(selected_model)
        return client

    if provider_type == "remote_ollama":
        if provider_config is None or not provider_config.base_url:
            raise ValueError("Remote Ollama Base URL is required.")
        model_name = (provider_config.model_name or selected_model or "").strip()
        if not model_name:
            raise ValueError("Remote Ollama model name is required.")
        if not is_selectable_chat_model(model_name):
            raise ValueError(f"Model is not selectable for chat generation: {model_name}")
        return OllamaChatClient().with_base_url(provider_config.base_url).with_model(model_name)

    if provider_type == "openai_compatible":
        if provider_config is None or not provider_config.base_url:
            raise ValueError("OpenAI-compatible API Base URL is required.")
        if not provider_config.api_key:
            raise ValueError("OpenAI-compatible API key is required.")
        model_name = (provider_config.model_name or selected_model or "").strip()
        if not model_name:
            raise ValueError("OpenAI-compatible model name is required.")
        default_timeout = OllamaChatClient().settings.timeout_seconds
        return OpenAICompatibleChatClient(
            OpenAICompatibleSettings(
                base_url=normalize_base_url(provider_config.base_url),
                model=model_name,
                api_key=provider_config.api_key,
                timeout_seconds=default_timeout,
            )
        )

    if provider_type == "research_api":
        if provider_config is None or not provider_config.base_url:
            raise ValueError("Research API endpoint URL is required.")
        if not provider_config.api_key:
            raise ValueError("Research API key is required.")
        default_timeout = OllamaChatClient().settings.timeout_seconds
        return ResearchApiChatClient(
            ResearchApiSettings(
                endpoint_url=normalize_base_url(provider_config.base_url),
                api_key=provider_config.api_key,
                model=(provider_config.model_name or "remote-research-api").strip() or "remote-research-api",
                timeout_seconds=default_timeout,
            )
        )

    if provider_type == "custom_endpoint":
        raise ValueError("Custom endpoint provider is reserved for future extension.")

    raise ValueError(f"Unsupported model provider type: {provider_type}")


def _resolve_selected_model_for_provider(request: ChatRequest | HybridAnalysisRequest) -> str | None:
    if _provider_type(request.provider_config) in {"openai_compatible", "research_api"}:
        return None
    return request.resolved_selected_model()


def _normalize_selected_symbol(symbol: str) -> str:
    candidate = (symbol or "").strip().upper()
    if candidate in SUPPORTED_SYMBOL_ALIASES:
        return candidate
    for canonical, aliases in SUPPORTED_SYMBOL_ALIASES.items():
        if candidate in {alias.upper() for alias in aliases}:
            return canonical
    return candidate


def _detect_question_symbols(question: str) -> list[str]:
    detected: list[str] = []
    for canonical, aliases in SUPPORTED_SYMBOL_ALIASES.items():
        for alias in aliases:
            pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
            if re.search(pattern, question, flags=re.IGNORECASE):
                detected.append(canonical)
                break
    return detected


def _has_comparison_intent(question: str) -> bool:
    normalized = re.sub(r"\s+", " ", question.strip().lower())
    return any(
        re.search(rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])", normalized)
        for keyword in COMPARISON_KEYWORDS
    )


def _symbol_guardrail_response(selected_symbol: str, question: str) -> dict[str, Any] | None:
    selected = _normalize_selected_symbol(selected_symbol)
    question_symbols = _detect_question_symbols(question)
    unique_question_symbols = list(dict.fromkeys(question_symbols))

    if not unique_question_symbols:
        return None

    if len(unique_question_symbols) > 1 or (_has_comparison_intent(question) and selected not in unique_question_symbols):
        return {
            "guardrail_triggered": True,
            "guardrail_type": "multi_asset_question",
            "selected_symbol": selected,
            "question_symbol": ", ".join(unique_question_symbols),
            "message": (
                "This question mentions multiple assets. The current analysis mode supports one selected asset "
                "at a time. Please select one asset or use a future multi-asset comparison mode."
            ),
            "suggested_action": "Select one asset in the UI and ask a single-asset question.",
            "response_mode": "symbol_guardrail",
            "generation_mode": "guardrail",
            "model_used": "none",
            "prompt_context_type": "none",
            "news_context_included": False,
            "rag_context_included": False,
            "defillama_context_included": False,
            "included_news_context": False,
            "included_rag_context": False,
            "included_defillama_context": False,
            "fallback_happened": False,
        }

    question_symbol = unique_question_symbols[0]
    if question_symbol == selected:
        return None

    return {
        "guardrail_triggered": True,
        "guardrail_type": "symbol_mismatch",
        "selected_symbol": selected,
        "question_symbol": question_symbol,
        "message": (
            f"Your selected symbol is {selected}, but the question appears to ask about {question_symbol}. "
            "Analysis was stopped to avoid mixing market data, RAG context, news, and LLM generation for different assets."
        ),
        "suggested_action": f"Switch the selected symbol to {question_symbol}, or rewrite the question for {selected}.",
        "response_mode": "symbol_guardrail",
        "generation_mode": "guardrail",
        "model_used": "none",
        "prompt_context_type": "none",
        "news_context_included": False,
        "rag_context_included": False,
        "defillama_context_included": False,
        "included_news_context": False,
        "included_rag_context": False,
        "included_defillama_context": False,
        "fallback_happened": False,
    }


app = FastAPI(
    title="Web3 Finance LLM Backend",
    version="0.1.0",
    description="MVP FastAPI backend for local Ollama-powered crypto market insight chat.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=ApiResponse)
def root() -> ApiResponse:
    return ApiResponse(
        success=True,
        data={
            "service": "web3-finance-llm-backend",
            "message": "Backend is running. Open /docs for API documentation or use the React UI at http://127.0.0.1:5173.",
            "docs_url": "http://127.0.0.1:8000/docs",
            "health_url": "http://127.0.0.1:8000/health",
        },
    )


@app.get("/health", response_model=ApiResponse)
def health() -> ApiResponse:
    client = OllamaChatClient()
    ollama_status = client.health()
    return ApiResponse(
        success=True,
        data={
            "service": "web3-finance-llm-backend",
            "status": "ok",
            "ollama": ollama_status,
        },
    )


@app.get("/runtime/status", response_model=ApiResponse)
def runtime_status() -> ApiResponse:
    client = OllamaChatClient()
    ollama_status = client.health()
    available_models = ollama_status.get("available_models") or []
    chat_model = ollama_status.get("model")
    embedding_model = get_embedding_model_name()
    embedding_candidates = {embedding_model, f"{embedding_model}:latest"}
    embedding_available = any(model in available_models for model in embedding_candidates)

    components = [
        _status_item(
            "FastAPI backend",
            "ok",
            "FastAPI is responding and serving JSON endpoints.",
            details={
                "base_url": os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000"),
                "docs_url": "http://127.0.0.1:8000/docs",
                "health_url": "http://127.0.0.1:8000/health",
            },
        ),
        _status_item(
            "Ollama chat model",
            "ok" if ollama_status.get("reachable") and ollama_status.get("model_available") else "error",
            (
                f"Chat model is reachable: {chat_model}."
                if ollama_status.get("reachable") and ollama_status.get("model_available")
                else ollama_status.get("message") or f"Configured chat model is not available: {chat_model}."
            ),
            details={
                "base_url": ollama_status.get("base_url"),
                "model": chat_model,
                "model_available": ollama_status.get("model_available"),
            },
        ),
        _ollama_generation_status(client),
        _status_item(
            "Ollama embeddings",
            "ok" if ollama_status.get("reachable") and embedding_available else "error",
            (
                f"Embedding model is available: {embedding_model}."
                if ollama_status.get("reachable") and embedding_available
                else f"Embedding model is not available in Ollama: {embedding_model}."
            ),
            details={
                "base_url": ollama_status.get("base_url"),
                "model": embedding_model,
                "model_available": embedding_available,
            },
        ),
        _rag_index_status(),
        _market_provider_status(),
        _news_provider_status(),
        _defillama_status(),
    ]

    summary_status = "ok"
    if any(component["status"] == "error" for component in components):
        summary_status = "error"
    elif any(component["status"] == "warning" for component in components):
        summary_status = "warning"

    return ApiResponse(
        success=True,
        data={
            "status": summary_status,
            "context_strategy": "Smart Context Selection",
            "frontend": {
                "name": "React final UI",
                "expected_url": "http://127.0.0.1:5173",
                "role": "presentation_testing_ui",
            },
            "components": components,
        },
        sources=["fastapi:/runtime/status", "ollama:/api/tags"],
    )


@app.get("/models/ollama", response_model=ApiResponse)
def ollama_models() -> Any:
    client = OllamaChatClient()
    try:
        data = client.list_models()
    except OllamaClientError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(
                        code="OLLAMA_MODELS_UNAVAILABLE",
                        message=f"Ollama is not running or local models cannot be detected. {exc}",
                    ),
                    sources=[],
                )
            ),
        )

    return ApiResponse(success=True, data=data, sources=["ollama:/api/tags"])


@app.post("/models/test-connection", response_model=ApiResponse)
def test_model_connection(request: TestModelConnectionRequest) -> Any:
    provider_config = request.provider_config
    provider_type = provider_config.normalized_type()
    try:
        if provider_type == "local_ollama":
            data = OllamaChatClient().list_models()
            data["provider_type"] = provider_type
            return ApiResponse(success=True, data=data, sources=["ollama:/api/tags"])

        if provider_type == "remote_ollama":
            if not provider_config.base_url:
                raise ValueError("Remote Ollama Base URL is required.")
            data = OllamaChatClient().with_base_url(provider_config.base_url).list_models()
            data["provider_type"] = provider_type
            return ApiResponse(success=True, data=data, sources=["remote-ollama:/api/tags"])

        if provider_type == "openai_compatible":
            client = _resolve_model_client(provider_config)
            data = client.list_models()
            data["provider_type"] = provider_type
            return ApiResponse(success=True, data=data, sources=["openai-compatible:/models"])

        if provider_type == "research_api":
            client = _resolve_model_client(provider_config)
            data = client.list_models()
            data["provider_type"] = provider_type
            return ApiResponse(success=True, data=data, sources=["research-api:/v1/research/ask"])

        if provider_type == "custom_endpoint":
            raise ValueError("Custom endpoint provider is reserved for future extension.")

        raise ValueError(f"Unsupported model provider type: {provider_type}")
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="INVALID_MODEL_PROVIDER", message=str(exc)),
                    sources=[],
                )
            ),
        )
    except OllamaClientError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="MODEL_PROVIDER_CONNECTION_FAILED", message=str(exc)),
                    sources=[],
                )
            ),
        )


@app.post("/chat", response_model=ApiResponse)
def chat(request: ChatRequest) -> Any:
    try:
        selected_model = _resolve_selected_model_for_provider(request)
        client = _resolve_model_client(request.provider_config, selected_model)
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="INVALID_CHAT_MODEL", message=str(exc)),
                    sources=request.sources,
                )
            ),
        )

    try:
        answer = client.chat(
            message=request.message,
            system_prompt=request.system_prompt,
            context=request.context,
        )
    except OllamaClientError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="OLLAMA_CHAT_FAILED", message=str(exc)),
                    sources=request.sources,
                )
            ),
        )

    return ApiResponse(
        success=True,
        data={
            "answer": answer,
            "model": client.settings.model,
            "model_used": client.settings.model,
            "selected_model": client.settings.model,
            "provider_type": _provider_type(request.provider_config),
        },
        sources=request.sources,
    )


@app.get("/market/{symbol}", response_model=ApiResponse)
def market(symbol: str) -> Any:
    service = MarketDataService()
    try:
        data, sources = service.get_market_snapshot(symbol)
    except MarketDataServiceError as exc:
        return JSONResponse(
            status_code=_market_error_status(exc),
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code=_market_error_code("MARKET_DATA_FAILED", exc), message=str(exc)),
                    sources=[],
                )
            ),
        )

    return ApiResponse(success=True, data=data, sources=sources)


@app.post("/analyze-basic", response_model=ApiResponse)
def analyze_basic(request: BasicAnalysisRequest) -> Any:
    service = MarketDataService()
    try:
        data, sources = service.analyze_basic(
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.limit,
        )
    except MarketDataServiceError as exc:
        return JSONResponse(
            status_code=_market_error_status(exc),
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code=_market_error_code("BASIC_ANALYSIS_FAILED", exc), message=str(exc)),
                    sources=[],
                )
            ),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="INVALID_ANALYSIS_INPUT", message=str(exc)),
                    sources=[],
                )
            ),
        )

    return ApiResponse(success=True, data=data, sources=sources)


@app.get("/news/{symbol}", response_model=ApiResponse)
def news(symbol: str, limit: int = Query(default=6, ge=1, le=12)) -> Any:
    service = LiveNewsService(max_articles=limit)
    try:
        data, sources = service.fetch_relevant_news(symbol=symbol)
    except MarketDataServiceError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="INVALID_NEWS_SYMBOL", message=str(exc)),
                    sources=[],
                )
            ),
        )

    return ApiResponse(success=True, data=data, sources=sources)


@app.post("/analyze", response_model=ApiResponse)
def analyze(request: HybridAnalysisRequest) -> Any:
    try:
        question = request.resolved_question()
        guardrail_data = _symbol_guardrail_response(request.symbol, question)
        if guardrail_data:
            return ApiResponse(success=True, data=guardrail_data, sources=[])

        selected_model = _resolve_selected_model_for_provider(request)
        client = _resolve_model_client(request.provider_config, selected_model)
        service = HybridAnalysisService(llm_client=client)
        data, sources = service.analyze(
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.limit,
            question=question,
        )
        data["provider_type"] = _provider_type(request.provider_config)
    except MarketDataServiceError as exc:
        return JSONResponse(
            status_code=_market_error_status(exc),
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code=_market_error_code("MARKET_DATA_FAILED", exc), message=str(exc)),
                    sources=[],
                )
            ),
        )
    except HybridAnalysisServiceError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="HYBRID_ANALYSIS_FAILED", message=str(exc)),
                    sources=[],
                )
            ),
        )
    except RuntimeError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="HYBRID_ANALYSIS_FAILED", message=str(exc)),
                    sources=[],
                )
            ),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="INVALID_ANALYSIS_INPUT", message=str(exc)),
                    sources=[],
                )
            ),
        )

    return ApiResponse(success=True, data=data, sources=sources)


@app.post("/predict", response_model=ApiResponse)
def predict(request: PredictionRequest) -> Any:
    service = PredictionService()
    try:
        data, sources = service.predict_market(
            symbol=request.symbol,
            timeframe=request.timeframe,
            horizon_candles=request.resolved_horizon_candles(),
            limit=request.limit,
        )
    except MarketDataServiceError as exc:
        return JSONResponse(
            status_code=_market_error_status(exc),
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code=_market_error_code("PREDICTION_MARKET_DATA_FAILED", exc), message=str(exc)),
                    sources=[],
                )
            ),
        )
    except PredictionServiceError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="PREDICTION_FAILED", message=str(exc)),
                    sources=[],
                )
            ),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="INVALID_PREDICTION_INPUT", message=str(exc)),
                    sources=[],
                )
            ),
        )

    return ApiResponse(success=True, data=data, sources=sources)
