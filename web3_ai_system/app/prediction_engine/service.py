import pandas as pd

from app.prediction_engine.data_loader import build_demo_market_data
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
        demo_frame = build_demo_market_data()
        return self.train_and_predict(
            market_frame=demo_frame,
            asset=request.asset,
            horizon_days=request.horizon_days,
        )
