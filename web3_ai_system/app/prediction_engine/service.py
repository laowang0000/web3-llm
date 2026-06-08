from typing import Any

import pandas as pd

from app.market_data.service import MarketDataService, normalize_symbol
from app.prediction_engine.features import build_indicator_frame
from app.prediction_engine.preprocessing import validate_market_frame
from app.prediction_engine.trainer import PredictionTrainer
from app.schemas import PredictionResult, QueryRequest


FEATURE_SUMMARY = [
    "rsi",
    "ema_short",
    "ema_long",
    "ema_distance",
    "macd",
    "macd_signal",
    "macd_histogram",
    "bollinger_bandwidth",
    "rolling_volatility",
    "rolling_mean_return",
    "return_lag_1",
    "return_lag_2",
    "return_lag_3",
    "volume_change",
    "price_momentum",
    "atr_14_pct",
    "trend_strength_proxy",
]
DISCLAIMER = (
    "This is a backtest metric and does not guarantee future trading performance. "
    "This prediction is for academic demonstration only and is not financial advice."
)
DEMO_RECOMMENDED_SETTINGS = {
    "symbol": "BTCUSDT",
    "timeframes": ["4h", "1d"],
    "limit": "500 candles for the current demo; 1000+ for stronger validation",
    "horizon_candles": "3 to 5 future candles",
}


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
        horizon_candles: int,
    ) -> PredictionResult:
        cleaned = validate_market_frame(market_frame)
        model, feature_frame, metrics = self.trainer.train(
            market_frame=cleaned,
            horizon_candles=horizon_candles,
        )
        predicted_trend, probability_up = model.predict_latest(feature_frame)
        probability_down = round(1.0 - probability_up, 4)
        return PredictionResult(
            asset=asset,
            horizon_days=horizon_candles,
            horizon_candles=horizon_candles,
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
        horizon_candles: int = 3,
        horizon_days: int | None = None,
        limit: int = 300,
    ) -> tuple[dict[str, Any], list[str]]:
        if horizon_days is not None:
            horizon_candles = horizon_days
        normalized_symbol = normalize_symbol(symbol)
        ohlcv_frame, sources = self.market_service.get_ohlcv(
            symbol=normalized_symbol,
            timeframe=timeframe,
            limit=limit,
        )
        historical_provider = ohlcv_frame.attrs.get("provider") or (sources[0].split(":", 1)[0] if sources else None)
        source_warnings = []
        data_warning = ohlcv_frame.attrs.get("data_warning")
        if data_warning:
            source_warnings.append(data_warning)

        try:
            indicator_frame = build_indicator_frame(ohlcv_frame)
        except ValueError as exc:
            raise PredictionServiceError(str(exc)) from exc

        try:
            result = self.train_and_predict(
                market_frame=indicator_frame,
                asset=normalized_symbol,
                horizon_candles=horizon_candles,
            )
            metrics = {
                **(result.metrics or {}),
                "metric_type": "demo_backtest",
                "split_strategy": "Chronological train/test split",
                "leakage_control": (
                    "Indicators and model features use current/past rows only. "
                    "The future close is used only to create the target label and is not included in feature_columns."
                ),
            }
            interpretation = self._evaluation_interpretation(metrics)
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
            interpretation = {
                "target_85_achieved": False,
                "outperformed_baseline": False,
                "reliability": "Model metrics are unavailable because training failed; use this only as a technical-indicator fallback.",
                "summary": "The supervised prediction model did not produce a valid backtest for this request.",
            }
            notes = [
                "Supervised demo model could not be trained reliably for this request.",
                f"Fallback reason: {exc}",
                "Fallback uses latest RSI, EMA, MACD, Bollinger position, and volatility only.",
            ]

        sample_warning = self._sample_warning(limit, metrics)
        model_selection = (metrics or {}).get("model_selection") if metrics else {}
        if not isinstance(model_selection, dict):
            model_selection = {}
        data = {
            "symbol": normalized_symbol,
            "provider": historical_provider,
            "timeframe": timeframe,
            "horizon_candles": horizon_candles,
            "horizon_days": horizon_candles,
            "horizon_label": f"future {horizon_candles} candles",
            "predicted_trend": predicted_trend,
            "probability_up": probability_up,
            "probability_down": probability_down,
            "model_name": model_name,
            "metrics": metrics,
            "model_selection": model_selection,
            "model_candidates": model_selection.get("candidate_models", []),
            "features": FEATURE_SUMMARY,
            "evaluation": interpretation,
            "target_85_achieved": bool(metrics.get("target_85_achieved")) if metrics else False,
            "target_85_message": metrics.get("target_message") if metrics else interpretation["summary"],
            "sample_warning": sample_warning,
            "recommended_settings": DEMO_RECOMMENDED_SETTINGS,
            "disclaimer": DISCLAIMER,
            "chart_data": self._chart_data(indicator_frame),
        }
        if source_warnings:
            data["source_warnings"] = source_warnings
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
            horizon_candles=request.horizon_candles or request.horizon_days,
        )

    def _evaluation_interpretation(self, metrics: dict[str, Any]) -> dict[str, Any]:
        improvement = float(metrics.get("model_vs_baseline_improvement", 0) or 0)
        test_rows = int((metrics.get("support") or {}).get("total") or 0)
        target_achieved = bool(metrics.get("target_85_achieved"))
        if test_rows < 50:
            reliability = "Low reliability: the chronological test window has fewer than 50 labelled candles."
        elif improvement <= 0:
            reliability = "Mixed reliability: the model did not outperform the strongest simple baseline in this window."
        else:
            reliability = "More reliable for demonstration: the model outperformed the strongest simple baseline in this window."
        return {
            "target_85_achieved": target_achieved,
            "outperformed_baseline": improvement > 0,
            "reliability": reliability,
            "summary": (
                "The model outperformed baseline and reached the 85% demo target in this backtest window."
                if target_achieved and improvement > 0
                else metrics.get("target_message")
            ),
        }

    def _sample_warning(self, limit: int, metrics: dict[str, Any] | None) -> str | None:
        test_rows = int(((metrics or {}).get("support") or {}).get("total") or 0)
        if limit < 300:
            return "Sample size is below the recommended 300 candles; metrics may be unstable."
        if test_rows and test_rows < 50:
            return "The test window has fewer than 50 labelled candles; metrics may be unstable."
        return None

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
