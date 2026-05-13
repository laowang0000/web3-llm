from collections import Counter

from app.config import settings
from app.insight_engine.embeddings import EmbeddingClientError, build_embeddings, get_embedding_settings
from app.insight_engine.loaders import build_default_loader
from app.insight_engine.splitter import InsightChunker
from app.insight_engine.vector_store import InsightVectorStore


def _collection_name(provider: str, model: str) -> str:
    safe_model = "".join(character if character.isalnum() else "_" for character in model.lower())
    return f"crypto_insight_{provider}_{safe_model}"[:63]


def main() -> int:
    print("RAG pre-indexing")
    print("================")

    try:
        embedding_settings = get_embedding_settings()
        if embedding_settings.provider != "ollama":
            print(
                "ERROR: RAG pre-indexing expects local Ollama embeddings. "
                "Set EMBEDDING_PROVIDER=ollama in .env."
            )
            return 1

        print(f"Embedding provider: {embedding_settings.provider}")
        print(f"Embedding model: {embedding_settings.model}")
        print(f"Ollama base URL: {embedding_settings.base_url}")

        embeddings = build_embeddings(embedding_settings.model)
        embeddings.embed_query("health check")
    except EmbeddingClientError as exc:
        print(f"ERROR: Ollama embedding model is unavailable: {exc}")
        print("Fix: run `ollama serve` and `ollama pull nomic-embed-text`.")
        return 1
    except Exception as exc:
        print(f"ERROR: Could not initialize embeddings: {exc}")
        return 1

    loader = build_default_loader()
    documents = loader.load()
    if not documents:
        print("ERROR: No RAG documents found.")
        print(f"Checked: {settings.insight_data_dir}")
        print(f"Checked: {settings.rag_raw_dir}")
        return 1

    source_counts = Counter(
        f"{doc.metadata.get('source_type', 'unknown')}::{doc.metadata.get('source_name', 'unknown')}"
        for doc in documents
    )

    chunker = InsightChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = chunker.split(documents)
    if not chunks:
        print("ERROR: Documents loaded but no chunks were generated.")
        return 1

    vector_store = InsightVectorStore(
        persist_directory=settings.chroma_persist_dir,
        embeddings=embeddings,
        collection_name=_collection_name(embedding_settings.provider, embedding_settings.model),
    )

    try:
        indexed_count = vector_store.index_documents(chunks, force=True)
    except Exception as exc:
        print(f"ERROR: Failed to write Chroma index: {exc}")
        return 1

    print(f"Document pages/files loaded: {len(documents)}")
    print(f"Chunks generated: {len(chunks)}")
    print(f"Chunks indexed in Chroma: {indexed_count}")
    print(f"Chroma path: {settings.chroma_persist_dir}")
    print("Indexed sources:")
    for source, count in sorted(source_counts.items()):
        print(f"- {source}: {count} document item(s)")
    print("RAG pre-indexing completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
