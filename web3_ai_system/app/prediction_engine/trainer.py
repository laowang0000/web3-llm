import pandas as pd

from app.prediction_engine.features import build_feature_frame, get_feature_columns
from app.prediction_engine.model import XGBoostTrendClassifier
from app.prediction_engine.split import time_series_train_test_split


class PredictionTrainer:
    """Chronological training pipeline for trend classification."""

    def __init__(self) -> None:
        self.model = XGBoostTrendClassifier()

    def train(
        self,
        market_frame: pd.DataFrame,
        horizon_days: int,
    ) -> tuple[XGBoostTrendClassifier, pd.DataFrame, dict[str, float]]:
        feature_frame = build_feature_frame(market_frame, horizon_days=horizon_days)
        feature_columns = get_feature_columns()
        train_frame, test_frame = time_series_train_test_split(feature_frame, test_ratio=0.2)
        self.model.fit(train_frame, feature_columns)
        metrics = self.model.evaluate(test_frame)
        return self.model, feature_frame, metrics
