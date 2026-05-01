from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings


class InsightVectorStore:
    """Chroma-backed vector store for RAG retrieval."""

    def __init__(
        self,
        persist_directory: Path,
        embeddings: OpenAIEmbeddings,
        collection_name: str = "crypto_insight_documents",
    ) -> None:
        self.persist_directory = persist_directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(self.persist_directory),
        )

    def index_documents(self, documents: list[Document]) -> None:
        if not documents:
            return
        if self.store._collection.count() > 0:
            return
        self.store.add_documents(documents)

    def as_retriever(self, k: int = 4):
        return self.store.as_retriever(search_kwargs={"k": k})
