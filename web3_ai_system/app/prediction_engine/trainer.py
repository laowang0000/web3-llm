import pandas as pd

from app.prediction_engine.features import build_feature_frame, get_feature_columns
from app.prediction_engine.model import TrendClassifier
from app.prediction_engine.split import time_series_train_test_split


class PredictionTrainer:
    """Chronological training pipeline for trend classification."""

    def __init__(self) -> None:
        self.model = TrendClassifier()

    def train(
        self,
        market_frame: pd.DataFrame,
        horizon_candles: int,
    ) -> tuple[TrendClassifier, pd.DataFrame, dict[str, object]]:
        feature_frame = build_feature_frame(market_frame, horizon_candles=horizon_candles)
        if len(feature_frame) < 80:
            raise ValueError("At least 80 usable feature rows are required for demo model training.")
        feature_columns = get_feature_columns()
        forbidden_columns = {"future_price", "target_future_close", "target", "target_label"}
        leakage_columns = sorted(forbidden_columns.intersection(feature_columns))
        if leakage_columns:
            raise ValueError(f"Potential leakage columns cannot be used as features: {leakage_columns}")
        train_frame, test_frame = time_series_train_test_split(feature_frame, test_ratio=0.2)
        if train_frame["target"].nunique() < 2:
            raise ValueError("Training target contains only one class; model metrics would be unreliable.")
        self.model, metrics = self._train_best_candidate(train_frame, test_frame, feature_columns)
        metrics["split"] = {
            "strategy": "chronological_train_test_split",
            "shuffle": False,
            "train_rows": int(len(train_frame)),
            "test_rows": int(len(test_frame)),
            "train_start": str(train_frame["timestamp"].iloc[0]) if "timestamp" in train_frame else None,
            "train_end": str(train_frame["timestamp"].iloc[-1]) if "timestamp" in train_frame else None,
            "test_start": str(test_frame["timestamp"].iloc[0]) if "timestamp" in test_frame else None,
            "test_end": str(test_frame["timestamp"].iloc[-1]) if "timestamp" in test_frame else None,
        }
        return self.model, feature_frame, metrics

    def _train_best_candidate(
        self,
        train_frame: pd.DataFrame,
        test_frame: pd.DataFrame,
        feature_columns: list[str],
    ) -> tuple[TrendClassifier, dict[str, object]]:
        candidate_factory = TrendClassifier()
        candidate_summaries: list[dict[str, object]] = []
        candidate_failures: list[dict[str, str]] = []
        best_model: TrendClassifier | None = None
        best_metrics: dict[str, object] | None = None
        best_score: tuple[float, float, float] | None = None

        for model_name, estimator in candidate_factory.candidate_models(train_frame["target"]):
            candidate = TrendClassifier()
            try:
                candidate.fit_candidate(train_frame, feature_columns, model_name, estimator)
                metrics = candidate.evaluate(train_frame, test_frame)
            except Exception as exc:
                candidate_failures.append({"model_name": model_name, "error": str(exc)})
                continue

            accuracy = float(metrics.get("accuracy", 0) or 0)
            f1 = float(metrics.get("f1", 0) or 0)
            improvement = float(metrics.get("model_vs_baseline_improvement", 0) or 0)
            score = (accuracy, f1, improvement)
            candidate_summaries.append(
                {
                    "model_name": model_name,
                    "accuracy": accuracy,
                    "precision": metrics.get("precision"),
                    "recall": metrics.get("recall"),
                    "f1": f1,
                    "baseline_accuracy": metrics.get("baseline_accuracy"),
                    "model_vs_baseline_improvement": improvement,
                    "target_85_achieved": metrics.get("target_85_achieved"),
                    "selected": False,
                }
            )
            if best_score is None or score > best_score:
                best_model = candidate
                best_metrics = metrics
                best_score = score

        if best_model is None or best_metrics is None:
            failure_text = "; ".join(
                f"{item['model_name']}: {item['error']}" for item in candidate_failures
            )
            raise ValueError(f"No candidate prediction model could be trained. {failure_text}")

        for summary in candidate_summaries:
            summary["selected"] = summary["model_name"] == best_model.model_name

        best_metrics["model_selection"] = {
            "strategy": "best_accuracy_on_chronological_test_split",
            "selected_model": best_model.model_name,
            "selection_metric": "accuracy",
            "tie_breakers": ["f1", "model_vs_baseline_improvement"],
            "candidate_count": len(candidate_summaries),
            "candidate_models": candidate_summaries,
            "failed_candidates": candidate_failures,
        }
        return best_model, best_metrics
