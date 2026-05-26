from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RouteType(str, Enum):
    INSIGHT = "insight"
    PREDICTION = "prediction"
    HYBRID = "hybrid"


@dataclass
class QueryRequest:
    user_query: str
    asset: str = "BTC"
    horizon_days: int = 3


@dataclass
class InsightResult:
    answer: str
    sources: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PredictionResult:
    asset: str
    horizon_days: int
    predicted_trend: str
    probability_up: float | None
    model_name: str
    probability_down: float | None = None
    metrics: dict[str, Any] | None = None
    features: list[str] = field(default_factory=list)


@dataclass
class UnifiedResponse:
    route: RouteType
    insight: InsightResult | None = None
    prediction: PredictionResult | None = None


@dataclass
class BackendResponse:
    route: str
    prediction: str | None = None
    explanation: str | None = None
    final_output: str = ""
    sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
