from app.backend.service import HybridBackendService
from app.schemas import BackendResponse, QueryRequest


class Application:
    def __init__(self) -> None:
        self.backend = HybridBackendService()

    def handle_query(self, request: QueryRequest) -> BackendResponse:
        return self.backend.handle_query(request)


def build_application() -> Application:
    return Application()
