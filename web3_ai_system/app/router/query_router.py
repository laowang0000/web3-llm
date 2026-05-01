from app.router.intent_classifier import IntentClassifier
from app.schemas import QueryRequest, RouteType, UnifiedResponse


class QueryRouter:
    def __init__(self, insight_service, prediction_service) -> None:
        self.classifier = IntentClassifier()
        self.insight_service = insight_service
        self.prediction_service = prediction_service

    def route(self, request: QueryRequest) -> UnifiedResponse:
        route = self.classifier.classify(request)

        if route == RouteType.PREDICTION:
            return UnifiedResponse(
                route=route,
                prediction=self.prediction_service.predict(request),
            )

        return UnifiedResponse(
            route=route,
            insight=self.insight_service.generate(request),
        )
