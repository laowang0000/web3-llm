from langchain_core.documents import Document


class TopKInsightRetriever:
    """Thin wrapper to keep retrieval behavior explicit and testable."""

    def __init__(self, vector_store, k: int) -> None:
        self.retriever = vector_store.as_retriever(k=k)

    def retrieve(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)
