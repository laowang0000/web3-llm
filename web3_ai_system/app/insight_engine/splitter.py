from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class InsightChunker:
    """Chunks documents while preserving source metadata for traceability."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def split(self, documents: list[Document]) -> list[Document]:
        return self.splitter.split_documents(documents)
