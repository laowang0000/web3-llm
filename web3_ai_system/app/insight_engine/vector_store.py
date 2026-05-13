from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document


class InsightVectorStore:
    """Chroma-backed vector store for RAG retrieval."""

    def __init__(
        self,
        persist_directory: Path,
        embeddings: Any,
        collection_name: str = "crypto_insight_documents",
    ) -> None:
        self.persist_directory = persist_directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(self.persist_directory),
        )

    def index_documents(self, documents: list[Document], force: bool = False) -> int:
        if not documents:
            return self.store._collection.count()
        existing_count = self.store._collection.count()
        if existing_count == 0 or force:
            if force and existing_count > 0:
                ids = self.store._collection.get(include=[])["ids"]
                if ids:
                    self.store._collection.delete(ids=ids)
            self.store.add_documents(documents)
        return self.store._collection.count()

    def as_retriever(self, k: int = 4):
        return self.store.as_retriever(search_kwargs={"k": k})
