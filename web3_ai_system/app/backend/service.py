from app.backend.composer import build_final_output, build_prediction_text
from app.insight_engine.service import InsightService
from app.prediction_engine.service import PredictionService
from app.router.intent_classifier import classify_query_intent
from app.schemas import BackendResponse, QueryRequest


class HybridBackendService:
    """
    Integrates query routing, prediction, and RAG explanation into one backend flow.

    Flow:
    1. User query
    2. Query classification
    3. Route to correct module
    4. Generate output
    """

    def __init__(self) -> None:
        self.insight_service: InsightService | None = None
        self.prediction_service = PredictionService()

    def _get_insight_service(self) -> InsightService:
        if self.insight_service is None:
            self.insight_service = InsightService()
        return self.insight_service

    def handle_query(self, request: QueryRequest) -> BackendResponse:
        route = classify_query_intent(request.user_query)

        if route == "prediction":
            prediction = self.prediction_service.predict(request)
            insight = self._get_insight_service().generate(request)
            final_output = build_final_output(prediction=prediction, insight=insight)
            return BackendResponse(
                route=route,
                prediction=build_prediction_text(prediction),
                explanation=insight.answer,
                final_output=final_output,
                sources=insight.sources,
                metadata={
                    "model_name": prediction.model_name,
                    "probability_up": prediction.probability_up,
                    "metrics": prediction.metrics,
                },
            )

        insight = self._get_insight_service().generate(request)
        final_output = build_final_output(insight=insight)
        return BackendResponse(
            route=route,
            explanation=insight.answer,
            final_output=final_output,
            sources=insight.sources,
        )
