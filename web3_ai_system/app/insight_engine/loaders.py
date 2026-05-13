from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from app.config import settings


class InsightDocumentLoader:
    """Loads text, markdown, and PDF source documents for local RAG."""

    def __init__(self, data_dir: Path, extra_source_dirs: dict[str, Path] | None = None) -> None:
        self.data_dir = data_dir
        self.extra_source_dirs = extra_source_dirs or {}

    def load(self) -> list[Document]:
        directories = {
            "crypto_news": self.data_dir / "crypto_news",
            "on_chain_summaries": self.data_dir / "on_chain_summaries",
            "market_reports": self.data_dir / "market_reports",
            **self.extra_source_dirs,
        }

        documents: list[Document] = []
        for source_type, directory in directories.items():
            if not directory.exists():
                continue

            source_documents: list[Document] = []
            for path in self._iter_supported_files(directory):
                try:
                    if path.suffix.lower() == ".pdf":
                        source_documents.extend(PyPDFLoader(str(path)).load())
                    else:
                        source_documents.extend(TextLoader(str(path), encoding="utf-8").load())
                except Exception:
                    continue

            for doc in source_documents:
                doc.metadata["source_type"] = source_type
                doc.metadata["source_name"] = Path(doc.metadata.get("source", "")).name
                doc.metadata["source_path"] = str(doc.metadata.get("source", ""))
                doc.metadata["file_extension"] = Path(doc.metadata.get("source", "")).suffix.lower()

            documents.extend(source_documents)

        return documents

    def _iter_supported_files(self, directory: Path):
        for extension in ("*.txt", "*.md", "*.pdf"):
            yield from directory.rglob(extension)


def build_default_loader() -> InsightDocumentLoader:
    extra_dirs = {}
    if settings.rag_raw_dir.exists():
        extra_dirs["rag_raw"] = settings.rag_raw_dir
    return InsightDocumentLoader(settings.insight_data_dir, extra_source_dirs=extra_dirs)
