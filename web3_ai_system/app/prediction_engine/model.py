import pandas as pd
from xgboost import XGBClassifier


class XGBoostTrendClassifier:
    model_name = "xgboost_trend_classifier"

    def __init__(self) -> None:
        self.model = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=42,
        )
        self.feature_columns: list[str] = []

    def fit(self, train_frame: pd.DataFrame, feature_columns: list[str]) -> None:
        self.feature_columns = feature_columns
        self.model.fit(train_frame[feature_columns], train_frame["target"])

    def predict_latest(self, feature_frame: pd.DataFrame) -> tuple[str, float]:
        latest_row = feature_frame[self.feature_columns].tail(1)
        probability_up = float(self.model.predict_proba(latest_row)[0][1])
        predicted_trend = "UP" if probability_up >= 0.5 else "DOWN"
        return predicted_trend, round(probability_up, 4)

    def evaluate(self, test_frame: pd.DataFrame) -> dict[str, float]:
        probabilities = self.model.predict_proba(test_frame[self.feature_columns])[:, 1]
        predictions = (probabilities >= 0.5).astype(int)
        actual = test_frame["target"]

        accuracy = float((predictions == actual).mean())
        precision = float(
            ((predictions == 1) & (actual == 1)).sum() / max((predictions == 1).sum(), 1)
        )
        recall = float(
            ((predictions == 1) & (actual == 1)).sum() / max((actual == 1).sum(), 1)
        )
        return {
            "accuracy": round(accuracy, 4),
            "precision_up": round(precision, 4),
            "recall_up": round(recall, 4),
        }
