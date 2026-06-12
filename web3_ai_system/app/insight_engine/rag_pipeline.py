from langchain_core.documents import Document
from typing import Any

from app.insight_engine.prompts import INSIGHT_PROMPT
from app.schemas import InsightResult, QueryRequest


class CryptoInsightRAGPipeline:
    """Runs retrieval and evidence-grounded reasoning for market insights."""

    def __init__(self, retriever, llm: Any) -> None:
        self.retriever = retriever
        self.llm = llm

    def _format_context(self, documents: list[Document]) -> str:
        blocks: list[str] = []
        for index, doc in enumerate(documents, start=1):
            source_name = doc.metadata.get("source_name", f"document_{index}")
            source_type = doc.metadata.get("source_type", "unknown")
            file_extension = doc.metadata.get("file_extension", "")
            page = self._display_page(doc.metadata.get("page"))
            page_label = f"; page={page}" if page is not None else ""
            blocks.append(
                f"[Document {index}] "
                f"source_name={source_name}; source_type={source_type}; file_extension={file_extension}{page_label}\n"
                f"{doc.page_content}"
            )
        return "\n\n".join(blocks)

    def _build_chunk_trace(self, documents: list[Document]) -> list[dict]:
        trace: list[dict] = []
        for doc in documents:
            trace.append(
                {
                    "source_name": doc.metadata.get("source_name", "unknown"),
                    "source_type": doc.metadata.get("source_type", "unknown"),
                    "file_extension": doc.metadata.get("file_extension", ""),
                    "page": self._display_page(doc.metadata.get("page")),
                    "preview": doc.page_content[:240].strip(),
                }
            )
        return trace

    def run(self, request: QueryRequest) -> InsightResult:
        documents = self.retriever.retrieve(request.user_query)
        context = self._format_context(documents)
        prompt = INSIGHT_PROMPT.invoke(
            {
                "question": request.user_query,
                "context": context or "No relevant context was retrieved.",
            }
        )
        response = self.llm.invoke(prompt)

        source_labels = []
        for doc in documents:
            label = f"{doc.metadata.get('source_type', 'unknown')}::{doc.metadata.get('source_name', 'unknown')}"
            page = self._display_page(doc.metadata.get("page"))
            if page is not None:
                label = f"{label}#page={page}"
            source_labels.append(label)

        return InsightResult(
            answer=response.content,
            sources=source_labels,
            retrieved_chunks=self._build_chunk_trace(documents),
        )

    def _display_page(self, page: object) -> int | None:
        if page is None:
            return None
        try:
            return int(page) + 1
        except (TypeError, ValueError):
            return None
