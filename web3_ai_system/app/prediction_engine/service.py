from typing import Any

import pandas as pd

from app.market_data.service import MarketDataService, normalize_symbol
from app.prediction_engine.features import build_indicator_frame
from app.prediction_engine.preprocessing import validate_market_frame
from app.prediction_engine.trainer import PredictionTrainer
from app.schemas import PredictionResult, QueryRequest


FEATURE_SUMMARY = ["close", "volume", "rsi", "ema", "macd", "bollinger", "volatility"]
DISCLAIMER = "This prediction is for academic demonstration only and is not financial advice."


class PredictionServiceError(RuntimeError):
    """Raised when trend prediction cannot be produced."""


class PredictionService:
    """Pure numerical prediction service with no LLM dependency."""

    def __init__(self, market_service: MarketDataService | None = None) -> None:
        self.trainer = PredictionTrainer()
        self.market_service = market_service or MarketDataService()

    def train_and_predict(
        self,
        market_frame: pd.DataFrame,
        asset: str,
        horizon_days: int,
    ) -> PredictionResult:
        cleaned = validate_market_frame(market_frame)
        model, feature_frame, metrics = self.trainer.train(
            market_frame=cleaned,
            horizon_days=horizon_days,
        )
        predicted_trend, probability_up = model.predict_latest(feature_frame)
        probability_down = round(1.0 - probability_up, 4)
        return PredictionResult(
            asset=asset,
            horizon_days=horizon_days,
            predicted_trend=predicted_trend,
            probability_up=probability_up,
            probability_down=probability_down,
            model_name=model.model_name,
            metrics=metrics,
            features=FEATURE_SUMMARY,
        )

    def predict_market(
        self,
        symbol: str,
        timeframe: str = "1d",
        horizon_days: int = 3,
        limit: int = 300,
    ) -> tuple[dict[str, Any], list[str]]:
        normalized_symbol = normalize_symbol(symbol)
        ohlcv_frame, sources = self.market_service.get_ohlcv(
            symbol=normalized_symbol,
            timeframe=timeframe,
            limit=limit,
        )

        try:
            indicator_frame = build_indicator_frame(ohlcv_frame)
        except ValueError as exc:
            raise PredictionServiceError(str(exc)) from exc

        try:
            result = self.train_and_predict(
                market_frame=indicator_frame,
                asset=normalized_symbol,
                horizon_days=horizon_days,
            )
            metrics = {
                **(result.metrics or {}),
                "metric_type": "demo_backtest",
                "split_strategy": "Chronological train/test split",
                "leakage_control": "Indicators use current/past rows only; target uses future close after feature creation.",
            }
            model_name = result.model_name
            predicted_trend = result.predicted_trend
            probability_up = result.probability_up
            probability_down = result.probability_down
            notes: list[str] = []
        except Exception as exc:
            fallback = self._technical_fallback(indicator_frame)
            metrics = None
            model_name = "TechnicalIndicatorFallback"
            predicted_trend = fallback["predicted_trend"]
            probability_up = fallback["probability_up"]
            probability_down = fallback["probability_down"]
            notes = [
                "XGBoost demo model could not be trained reliably for this request.",
                f"Fallback reason: {exc}",
                "Fallback uses latest RSI, EMA, MACD, Bollinger position, and volatility only.",
            ]

        data = {
            "symbol": normalized_symbol,
            "timeframe": timeframe,
            "horizon_days": horizon_days,
            "predicted_trend": predicted_trend,
            "probability_up": probability_up,
            "probability_down": probability_down,
            "model_name": model_name,
            "metrics": metrics,
            "features": FEATURE_SUMMARY,
            "disclaimer": DISCLAIMER,
            "chart_data": self._chart_data(indicator_frame),
        }
        if notes:
            data["notes"] = notes
        return data, sources

    def predict(self, request: QueryRequest) -> PredictionResult:
        ohlcv_frame, _ = self.market_service.get_ohlcv(
            symbol=request.asset,
            timeframe="1d",
            limit=max(240, request.horizon_days + 80),
        )
        market_frame = build_indicator_frame(ohlcv_frame)
        return self.train_and_predict(
            market_frame=market_frame,
            asset=request.asset,
            horizon_days=request.horizon_days,
        )

    def _technical_fallback(self, indicator_frame: pd.DataFrame) -> dict[str, Any]:
        latest = indicator_frame.tail(1).iloc[0]
        score = 0
        score += 1 if latest["close"] > latest["ema_20"] else -1
        score += 1 if latest["ema_20"] > latest["ema_50"] else -1
        score += 1 if latest["macd_histogram"] > 0 else -1
        if latest["rsi"] > 60:
            score += 1
        elif latest["rsi"] < 40:
            score -= 1
        if latest["close"] > latest["bollinger_middle"]:
            score += 1
        else:
            score -= 1

        probability_up = min(0.8, max(0.2, 0.5 + (score * 0.06)))
        probability_up = round(float(probability_up), 4)
        return {
            "predicted_trend": "UP" if probability_up >= 0.5 else "DOWN",
            "probability_up": probability_up,
            "probability_down": round(1.0 - probability_up, 4),
        }

    def _chart_data(self, indicator_frame: pd.DataFrame, rows: int = 120) -> list[dict[str, Any]]:
        columns = [
            "timestamp",
            "close",
            "rsi",
            "macd",
            "macd_signal",
            "macd_histogram",
        ]
        chart_frame = indicator_frame[columns].tail(rows).copy()
        chart_frame["timestamp"] = chart_frame["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return [
            {
                "timestamp": row["timestamp"],
                "close": round(float(row["close"]), 8),
                "rsi": round(float(row["rsi"]), 4),
                "macd": round(float(row["macd"]), 8),
                "macd_signal": round(float(row["macd_signal"]), 8),
                "macd_histogram": round(float(row["macd_histogram"]), 8),
            }
            for _, row in chart_frame.iterrows()
        ]
