from app.schemas import InsightResult, PredictionResult


def build_prediction_text(prediction: PredictionResult) -> str:
    direction = "increase" if prediction.predicted_trend == "UP" else "decrease"
    return (
        f"{prediction.asset} is likely to {direction} over the next "
        f"{prediction.horizon_days} day(s)."
    )


def build_final_output(
    prediction: PredictionResult | None = None,
    insight: InsightResult | None = None,
) -> str:
    parts: list[str] = []

    if prediction is not None:
        parts.append(f"Prediction: {build_prediction_text(prediction)}")

    if insight is not None:
        parts.append(f"Explanation: {insight.answer}")

    return "\n".join(parts).strip()
