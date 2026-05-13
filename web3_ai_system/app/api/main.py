from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.analysis.hybrid_service import HybridAnalysisService, HybridAnalysisServiceError
from app.llm.ollama_client import OllamaChatClient, OllamaClientError
from app.market_data.service import MarketDataService, MarketDataServiceError


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: ApiError | None = None
    sources: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question or instruction.")
    system_prompt: str | None = Field(
        default="You are a cryptocurrency market insight assistant. Explain clearly and avoid financial advice.",
        description="Optional system instruction for Ollama.",
    )
    context: str | None = Field(default=None, description="Optional retrieved context for prompt augmentation.")
    sources: list[str] = Field(default_factory=list, description="Optional source labels associated with context.")


class BasicAnalysisRequest(BaseModel):
    symbol: str = Field(..., min_length=2, description="Trading pair such as BTCUSDT, ETHUSDT, or SOLUSDT.")
    timeframe: str = Field(default="1h", description="Binance candle interval such as 15m, 1h, 4h, or 1d.")
    limit: int = Field(default=120, ge=50, le=1000, description="Number of candles to fetch.")


class HybridAnalysisRequest(BasicAnalysisRequest):
    question: str = Field(..., min_length=1, description="User question for the hybrid market analysis.")


def _response_content(response: ApiResponse) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return response.dict()


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


@app.post("/chat", response_model=ApiResponse)
def chat(request: ChatRequest) -> Any:
    client = OllamaChatClient()

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
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="MARKET_DATA_FAILED", message=str(exc)),
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
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="BASIC_ANALYSIS_FAILED", message=str(exc)),
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


@app.post("/analyze", response_model=ApiResponse)
def analyze(request: HybridAnalysisRequest) -> Any:
    try:
        service = HybridAnalysisService()
        data, sources = service.analyze(
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.limit,
            question=request.question,
        )
    except MarketDataServiceError as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_response_content(
                ApiResponse(
                    success=False,
                    data=None,
                    error=ApiError(code="MARKET_DATA_FAILED", message=str(exc)),
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
