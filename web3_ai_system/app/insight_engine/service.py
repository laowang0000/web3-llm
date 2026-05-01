from langchain_openai import ChatOpenAI

from app.config import settings
from app.insight_engine.embeddings import build_embeddings
from app.insight_engine.loaders import InsightDocumentLoader
from app.insight_engine.rag_pipeline import CryptoInsightRAGPipeline
from app.insight_engine.retriever import TopKInsightRetriever
from app.insight_engine.splitter import InsightChunker
from app.insight_engine.vector_store import InsightVectorStore
from app.schemas import InsightResult, QueryRequest


class InsightService:
    """High-level service for document-backed crypto market explanations."""

    def __init__(self) -> None:
        embeddings = build_embeddings(settings.embedding_model)
        loader = InsightDocumentLoader(settings.insight_data_dir)
        chunker = InsightChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        documents = loader.load()
        chunks = chunker.split(documents)

        vector_store = InsightVectorStore(
            persist_directory=settings.chroma_persist_dir,
            embeddings=embeddings,
        )
        if chunks:
            vector_store.index_documents(chunks)

        retriever = TopKInsightRetriever(
            vector_store=vector_store,
            k=settings.max_retrieved_documents,
        )
        llm = ChatOpenAI(model=settings.chat_model, temperature=0)
        self.pipeline = CryptoInsightRAGPipeline(retriever=retriever, llm=llm)

    def generate(self, request: QueryRequest) -> InsightResult:
        return self.pipeline.run(request)
