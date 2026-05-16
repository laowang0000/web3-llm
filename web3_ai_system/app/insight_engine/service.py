from app.config import settings
from app.insight_engine.embeddings import build_embeddings, get_embedding_settings
from app.insight_engine.loaders import build_default_loader
from app.insight_engine.retriever import TopKInsightRetriever
from app.insight_engine.splitter import InsightChunker
from app.insight_engine.vector_store import InsightVectorStore
from app.llm.ollama_client import OllamaChatClient
from app.schemas import InsightResult, QueryRequest


class InsightService:
    """High-level local RAG service for document-backed crypto market explanations."""

    def __init__(self) -> None:
        embedding_settings = get_embedding_settings()
        embeddings = build_embeddings(embedding_settings.model)
        vector_store = InsightVectorStore(
            persist_directory=settings.chroma_persist_dir,
            embeddings=embeddings,
            collection_name=self._collection_name(embedding_settings.provider, embedding_settings.model),
        )
        if vector_store.count() == 0:
            loader = build_default_loader()
            chunker = InsightChunker(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            documents = loader.load()
            chunks = chunker.split(documents)
            if chunks:
                vector_store.index_documents(chunks)

        self.retriever = TopKInsightRetriever(
            vector_store=vector_store,
            k=settings.max_retrieved_documents,
        )
        self.llm = OllamaChatClient()

    def generate(self, request: QueryRequest) -> InsightResult:
        documents = self.retrieve(request.user_query)
        context = self.format_context(documents)
        answer = self.llm.chat(
            message=request.user_query,
            system_prompt=(
                "You are a cryptocurrency insight analyst. Use only the retrieved context. "
                "If the context is insufficient, say so clearly. Avoid financial advice and unsupported claims."
            ),
            context=context or "No relevant context was retrieved.",
        )
        return InsightResult(
            answer=answer,
            sources=self.source_labels(documents),
            retrieved_chunks=self.chunk_metadata(documents),
        )

    def retrieve(self, query: str):
        return self.retriever.retrieve(query)

    def format_context(self, documents) -> str:
        blocks: list[str] = []
        for index, doc in enumerate(documents, start=1):
            source_name = doc.metadata.get("source_name", f"document_{index}")
            source_type = doc.metadata.get("source_type", "unknown")
            page = doc.metadata.get("page")
            page_label = f"; page={page}" if page is not None else ""
            blocks.append(
                f"[Context {index}] source_name={source_name}; source_type={source_type}{page_label}\n"
                f"{doc.page_content}"
            )
        return "\n\n".join(blocks)

    def source_labels(self, documents) -> list[str]:
        labels = []
        for doc in documents:
            source_type = doc.metadata.get("source_type", "unknown")
            source_name = doc.metadata.get("source_name", "unknown")
            page = doc.metadata.get("page")
            label = f"{source_type}::{source_name}"
            if page is not None:
                label = f"{label}#page={page}"
            labels.append(label)
        return labels

    def chunk_metadata(self, documents) -> list[dict]:
        chunks: list[dict] = []
        for doc in documents:
            chunks.append(
                {
                    "source_name": doc.metadata.get("source_name", "unknown"),
                    "source_type": doc.metadata.get("source_type", "unknown"),
                    "source_path": doc.metadata.get("source_path", ""),
                    "page": doc.metadata.get("page"),
                    "preview": doc.page_content[:240].strip(),
                }
            )
        return chunks

    def _collection_name(self, provider: str, model: str) -> str:
        safe_model = "".join(character if character.isalnum() else "_" for character in model.lower())
        return f"crypto_insight_{provider}_{safe_model}"[:63]
