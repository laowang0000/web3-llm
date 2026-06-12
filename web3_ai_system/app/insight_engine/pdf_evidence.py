import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from pypdf import PdfReader

from app.config import settings


DEFAULT_PDF_QUERY_TERMS = (
    "ethereum",
    "eth",
    "value",
    "risk",
    "staking",
    "supply",
    "burn",
    "fees",
    "l2",
    "layer 2",
)


def retrieve_explicit_pdf_documents(query: str, max_pages: int = 3) -> list[Document]:
    """Return real PDF pages when the user explicitly names a local PDF source."""
    pdf_paths = _matched_pdf_paths(query)
    if not pdf_paths:
        return []

    documents: list[Document] = []
    terms = _query_terms(query)
    for path in pdf_paths:
        documents.extend(_top_pages_for_pdf(path, terms=terms, max_pages=max_pages))
    return documents[:max_pages]


def format_documents_context(documents: list[Document]) -> str:
    blocks: list[str] = []
    for index, doc in enumerate(documents, start=1):
        source_name = doc.metadata.get("source_name", f"document_{index}")
        source_type = doc.metadata.get("source_type", "unknown")
        file_extension = doc.metadata.get("file_extension", "")
        page = doc.metadata.get("page")
        page_label = f"; page={page}" if page is not None else ""
        blocks.append(
            f"[Context {index}] source_name={source_name}; source_type={source_type}; "
            f"file_extension={file_extension}{page_label}\n"
            f"{doc.page_content}"
        )
    return "\n\n".join(blocks)


def source_labels(documents: list[Document]) -> list[str]:
    labels: list[str] = []
    for doc in documents:
        source_type = doc.metadata.get("source_type", "unknown")
        source_name = doc.metadata.get("source_name", "unknown")
        page = doc.metadata.get("page")
        label = f"{source_type}::{source_name}"
        if page is not None:
            label = f"{label}#page={page}"
        labels.append(label)
    return labels


def chunk_metadata(documents: list[Document]) -> list[dict[str, Any]]:
    return [
        {
            "source_name": doc.metadata.get("source_name", "unknown"),
            "source_type": doc.metadata.get("source_type", "unknown"),
            "source_path": doc.metadata.get("source_path", ""),
            "file_extension": doc.metadata.get("file_extension", ""),
            "page": doc.metadata.get("page"),
            "preview": doc.page_content[:240].strip(),
        }
        for doc in documents
    ]


def _matched_pdf_paths(query: str) -> list[Path]:
    normalized_query = _normalize(query)
    if ".pdf" not in normalized_query:
        return []

    paths: list[Path] = []
    for path in settings.rag_raw_dir.glob("*.pdf"):
        filename = path.name.lower()
        stem = path.stem.lower()
        normalized_stem = _normalize(stem)
        if filename in normalized_query or stem in normalized_query or normalized_stem in normalized_query:
            paths.append(path)
    return paths


def _top_pages_for_pdf(path: Path, *, terms: set[str], max_pages: int) -> list[Document]:
    try:
        reader = PdfReader(str(path))
    except Exception:
        return []

    scored_pages: list[tuple[int, int, str]] = []
    search_terms = terms | set(DEFAULT_PDF_QUERY_TERMS)
    for page_index, page in enumerate(reader.pages):
        try:
            text = " ".join((page.extract_text() or "").split())
        except Exception:
            continue
        if not text:
            continue
        lowered = text.lower()
        score = sum(lowered.count(term) for term in search_terms if len(term) >= 2)
        if score > 0:
            scored_pages.append((score, page_index, text))

    scored_pages.sort(key=lambda item: item[0], reverse=True)
    documents: list[Document] = []
    for _, page_index, text in scored_pages[:max_pages]:
        documents.append(
            Document(
                page_content=text[:1200],
                metadata={
                    "source_type": "rag_raw",
                    "source_name": path.name,
                    "source_path": str(path),
                    "file_extension": ".pdf",
                    "page": page_index + 1,
                    "retrieval_mode": "explicit_pdf",
                },
            )
        )
    return documents


def _query_terms(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-]{1,}", query.lower())
        if token not in {"the", "and", "for", "with", "pdf", "rag", "page", "cite", "risk"}
    }


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", value.lower()).strip("-")
