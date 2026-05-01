from collections.abc import Callable

from app.schemas import QueryRequest, RouteType


IntentCallback = Callable[[str], str]

PREDICTION_KEYWORDS = {
    "predict",
    "prediction",
    "forecast",
    "outlook",
    "trend",
    "price",
    "target",
    "tomorrow",
    "next day",
    "next week",
    "up",
    "down",
}

INSIGHT_KEYWORDS = {
    "why",
    "explain",
    "news",
    "insight",
    "reason",
    "because",
    "summary",
    "analyze",
    "analysis",
    "on-chain",
    "whale",
    "report",
    "sentiment",
}


def classify_query_intent(
    user_query: str,
    llm_classifier: IntentCallback | None = None,
) -> str:
    """
    Route a user query to either the insight engine or prediction engine.

    Rule-based routing is used first for speed, consistency, and safety.
    If the query is ambiguous, an optional LLM callback may be used as a fallback.

    Returns:
        "insight" or "prediction"
    """
    text = user_query.strip().lower()

    prediction_score = sum(keyword in text for keyword in PREDICTION_KEYWORDS)
    insight_score = sum(keyword in text for keyword in INSIGHT_KEYWORDS)

    if prediction_score > insight_score:
        return "prediction"
    if insight_score > prediction_score:
        return "insight"

    if llm_classifier is not None:
        llm_result = llm_classifier(user_query).strip().lower()
        if llm_result in {"insight", "prediction"}:
            return llm_result

    # Safe default:
    # ambiguous queries go to insight because narrative explanation is lower-risk
    # than accidentally treating a vague question as a forecast request.
    return "insight"


class IntentClassifier:
    """Adapter used by the wider app router."""

    def __init__(self, llm_classifier: IntentCallback | None = None) -> None:
        self.llm_classifier = llm_classifier

    def classify(self, request: QueryRequest) -> RouteType:
        intent = classify_query_intent(
            user_query=request.user_query,
            llm_classifier=self.llm_classifier,
        )
        if intent == "prediction":
            return RouteType.PREDICTION
        return RouteType.INSIGHT
