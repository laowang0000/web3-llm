from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from app.config import settings


def import_module_from_path(module_name: str, path: Path):
    spec = spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import module {module_name} from {path}")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def ensure_data_paths() -> dict[str, Path]:
    paths = {
        "base_dir": settings.base_dir,
        "insight_data_dir": settings.insight_data_dir,
        "crypto_news": settings.insight_data_dir / "crypto_news",
        "on_chain_summaries": settings.insight_data_dir / "on_chain_summaries",
        "market_reports": settings.insight_data_dir / "market_reports",
    }

    for name, path in paths.items():
        if name == "base_dir":
            continue
        path.mkdir(parents=True, exist_ok=True)
    return paths


def main() -> None:
    print("RAG Flow Setup Check")
    print("======================")

    paths = ensure_data_paths()
    print(f"Project root: {paths['base_dir']}")
    print(f"RAG code path: {paths['base_dir'] / 'app' / 'insight_engine'}")
    print(f"Insight data root: {paths['insight_data_dir']}")

    loaders_module = import_module_from_path(
        "rag_flow_loaders",
        paths['base_dir'] / "app" / "insight_engine" / "loaders.py",
    )
    splitter_module = import_module_from_path(
        "rag_flow_splitter",
        paths['base_dir'] / "app" / "insight_engine" / "splitter.py",
    )

    InsightDocumentLoader = loaders_module.InsightDocumentLoader
    InsightChunker = splitter_module.InsightChunker

    loader = InsightDocumentLoader(settings.insight_data_dir)
    documents = loader.load()
    print(f"Loaded documents: {len(documents)}")

    chunker = InsightChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = chunker.split(documents)
    print(f"Generated chunks: {len(chunks)}")

    print("\nData folders checked:")
    for folder in [paths["crypto_news"], paths["on_chain_summaries"], paths["market_reports"]]:
        file_count = sum(1 for _ in folder.rglob("*.txt")) + sum(1 for _ in folder.rglob("*.md"))
        print(f"- {folder}: {file_count} text/md files")

    print("\nNext step: set OPENAI_API_KEY and run Streamlit with `python run_streamlit.py`. ")


if __name__ == "__main__":
    main()
