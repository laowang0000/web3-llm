import pandas as pd

from app.market_data.service import MarketDataService
from app.prediction_engine.preprocessing import validate_market_frame
from app.prediction_engine.trainer import PredictionTrainer
from app.schemas import PredictionResult, QueryRequest


class PredictionService:
    """Pure numerical prediction service with no LLM dependency."""

    def __init__(self) -> None:
        self.trainer = PredictionTrainer()

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
        metrics.update(
            {
                "feature_set": ["price", "volume", "rsi", "ema", "macd"],
                "leakage_control": "Indicators use current/past rows only. Target uses future shift after feature creation.",
                "split_strategy": "Chronological train/test split",
            }
        )
        return PredictionResult(
            asset=asset,
            horizon_days=horizon_days,
            predicted_trend=predicted_trend,
            probability_up=probability_up,
            model_name=model.model_name,
            metrics=metrics,
        )

    def predict(self, request: QueryRequest) -> PredictionResult:
        market_service = MarketDataService()
        ohlcv_frame, _ = market_service.get_ohlcv(
            symbol=request.asset,
            timeframe="1d",
            limit=max(240, request.horizon_days + 80),
        )
        market_frame = ohlcv_frame.rename(columns={"close": "price"})[
            ["timestamp", "price", "volume"]
        ]
        return self.train_and_predict(
            market_frame=market_frame,
            asset=request.asset,
            horizon_days=request.horizon_days,
        )
