from typing import Any

import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover - depends on local environment
    XGBClassifier = None


class TrendClassifier:
    """Small time-series classifier wrapper with honest sklearn-style metrics."""

    def __init__(self) -> None:
        self.model: Any | None = None
        self.model_name = "UntrainedTrendClassifier"
        self.feature_columns: list[str] = []
        self.model_selection: dict[str, Any] = {}

    def fit(self, train_frame: pd.DataFrame, feature_columns: list[str]) -> None:
        self.feature_columns = feature_columns
        self.model = self._select_model(train_frame["target"])
        x_train = train_frame[self.feature_columns]
        y_train = train_frame["target"]
        self.model.fit(x_train, y_train)

    def fit_candidate(
        self,
        train_frame: pd.DataFrame,
        feature_columns: list[str],
        model_name: str,
        model: Any,
    ) -> None:
        self.feature_columns = feature_columns
        self.model_name = model_name
        self.model = model
        self.model_selection = {
            "strategy": "candidate_backtest_selection",
            "selected_model": model_name,
        }
        x_train = train_frame[self.feature_columns]
        y_train = train_frame["target"]
        self.model.fit(x_train, y_train)

    def predict_latest(self, feature_frame: pd.DataFrame) -> tuple[str, float]:
        if self.model is None:
            raise ValueError("Model has not been trained.")
        latest_row = feature_frame[self.feature_columns].tail(1)
        probability_up = float(self.model.predict_proba(latest_row)[0][1])
        predicted_trend = "UP" if probability_up >= 0.5 else "DOWN"
        return predicted_trend, round(probability_up, 4)

    def evaluate(self, train_frame: pd.DataFrame, test_frame: pd.DataFrame) -> dict[str, Any]:
        if self.model is None:
            raise ValueError("Model has not been trained.")

        probabilities = self.model.predict_proba(test_frame[self.feature_columns])[:, 1]
        predictions = (probabilities >= 0.5).astype(int)
        actual = test_frame["target"].astype(int)

        accuracy = float(accuracy_score(actual, predictions))
        majority_accuracy = self._majority_baseline_accuracy(train_frame, actual)
        previous_direction_accuracy = self._previous_direction_baseline_accuracy(test_frame, actual)
        baseline_accuracy = max(majority_accuracy, previous_direction_accuracy)
        matrix = confusion_matrix(actual, predictions, labels=[0, 1])
        support_down = int((actual == 0).sum())
        support_up = int((actual == 1).sum())
        target_85_achieved = accuracy >= 0.85

        return {
            "accuracy": round(accuracy, 4),
            "precision": round(float(precision_score(actual, predictions, zero_division=0)), 4),
            "recall": round(float(recall_score(actual, predictions, zero_division=0)), 4),
            "f1": round(float(f1_score(actual, predictions, zero_division=0)), 4),
            "confusion_matrix": {
                "labels": ["DOWN", "UP"],
                "matrix": matrix.astype(int).tolist(),
                "tn": int(matrix[0][0]),
                "fp": int(matrix[0][1]),
                "fn": int(matrix[1][0]),
                "tp": int(matrix[1][1]),
            },
            "support": {
                "DOWN": support_down,
                "UP": support_up,
                "total": int(len(actual)),
            },
            "baseline": {
                "majority_class": "UP" if int(train_frame["target"].mode().iloc[0]) == 1 else "DOWN",
                "majority_class_accuracy": round(majority_accuracy, 4),
                "previous_direction_accuracy": round(previous_direction_accuracy, 4),
                "baseline_accuracy": round(baseline_accuracy, 4),
            },
            "baseline_accuracy": round(baseline_accuracy, 4),
            "model_accuracy": round(accuracy, 4),
            "model_vs_baseline_improvement": round(accuracy - baseline_accuracy, 4),
            "target_85_achieved": target_85_achieved,
            "target_message": (
                "The model achieved the target demo accuracy in this backtest window."
                if target_85_achieved
                else "The model did not reach the 85% target in this backtest window. "
                "This may be due to market noise, limited candles, or weak directional signal."
            ),
            "warning": "This is a backtest metric and does not guarantee future trading performance.",
            "model_selection": self.model_selection,
        }

    def _select_model(self, y_train: pd.Series) -> Any:
        model_name, model = self._candidate_models(y_train)[0]
        self.model_name = model_name
        self.model_selection = {
            "strategy": "priority_model_selection",
            "selected_model": model_name,
            "reason": "XGBoost is used when available; otherwise the first balanced sklearn fallback is used.",
        }
        return model

    def candidate_models(self, y_train: pd.Series) -> list[tuple[str, Any]]:
        return self._candidate_models(y_train)

    def _candidate_models(self, y_train: pd.Series) -> list[tuple[str, Any]]:
        class_counts = y_train.value_counts()
        candidates: list[tuple[str, Any]] = []
        if XGBClassifier is not None and y_train.nunique() == 2:
            negative = int(class_counts.get(0, 1))
            positive = int(class_counts.get(1, 1))
            scale_pos_weight = max(0.2, min(5.0, negative / max(positive, 1)))
            candidates.append(
                (
                    "XGBoostTrendClassifier",
                    XGBClassifier(
                        n_estimators=160,
                        max_depth=3,
                        learning_rate=0.04,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        min_child_weight=3,
                        reg_lambda=2.0,
                        eval_metric="logloss",
                        random_state=42,
                        n_jobs=1,
                        scale_pos_weight=scale_pos_weight,
                    ),
                )
            )
            candidates.append(
                (
                    "XGBoostShallowTrendClassifier",
                    XGBClassifier(
                        n_estimators=120,
                        max_depth=2,
                        learning_rate=0.04,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        min_child_weight=5,
                        reg_lambda=4.0,
                        eval_metric="logloss",
                        random_state=42,
                        n_jobs=1,
                        scale_pos_weight=scale_pos_weight,
                    ),
                )
            )

        candidates.extend(
            [
                (
                    "RandomForestTrendClassifier",
                    RandomForestClassifier(
                        n_estimators=240,
                        max_depth=5,
                        min_samples_leaf=4,
                        class_weight="balanced",
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
                (
                    "ExtraTreesTrendClassifier",
                    ExtraTreesClassifier(
                        n_estimators=240,
                        max_depth=5,
                        min_samples_leaf=4,
                        class_weight="balanced",
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
                (
                    "GradientBoostingTrendClassifier",
                    GradientBoostingClassifier(
                        n_estimators=100,
                        max_depth=2,
                        learning_rate=0.04,
                        random_state=42,
                    ),
                ),
                (
                    "LogisticRegressionTrendClassifier",
                    make_pipeline(
                        StandardScaler(),
                        LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42),
                    ),
                ),
            ]
        )
        return candidates

    def _majority_baseline_accuracy(self, train_frame: pd.DataFrame, actual: pd.Series) -> float:
        majority_class = int(train_frame["target"].mode().iloc[0])
        baseline_predictions = [majority_class] * len(actual)
        return float(accuracy_score(actual, baseline_predictions))

    def _previous_direction_baseline_accuracy(self, test_frame: pd.DataFrame, actual: pd.Series) -> float:
        if "return_1" not in test_frame.columns:
            return 0.0
        baseline_predictions = (test_frame["return_1"].fillna(0) > 0).astype(int)
        return float(accuracy_score(actual, baseline_predictions))


class XGBoostTrendClassifier(TrendClassifier):
    """Backward-compatible class name used by older trainer code."""
