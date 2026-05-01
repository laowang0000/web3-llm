from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document


class InsightDocumentLoader:
    """Loads source documents from separate Web3 source folders."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def load(self) -> list[Document]:
        directories = {
            "crypto_news": self.data_dir / "crypto_news",
            "on_chain_summaries": self.data_dir / "on_chain_summaries",
            "market_reports": self.data_dir / "market_reports",
        }

        documents: list[Document] = []
        for source_type, directory in directories.items():
            if not directory.exists():
                continue

            source_documents: list[Document] = []
            for pattern in ("**/*.txt", "**/*.md"):
                loader = DirectoryLoader(
                    str(directory),
                    glob=pattern,
                    loader_cls=TextLoader,
                    loader_kwargs={"encoding": "utf-8"},
                    show_progress=False,
                )
                source_documents.extend(loader.load())

            for doc in source_documents:
                doc.metadata["source_type"] = source_type
                doc.metadata["source_name"] = Path(doc.metadata.get("source", "")).name

            documents.extend(source_documents)

        return documents
