from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()


def _int_setting(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "Web3 AI System"
    default_asset: str = "BTC"
    default_horizon_days: int = 3
    max_retrieved_documents: int = _int_setting("RAG_TOP_K", 3)
    base_dir: Path = BASE_DIR
    insight_data_dir: Path = base_dir / "data" / "insight_sources"
    rag_raw_dir: Path = base_dir.parent / "rag" / "raw"
    chroma_persist_dir: Path = base_dir / "storage" / "chroma_insight"
    embedding_model: str = "nomic-embed-text"
    chat_model: str = "qwen3.5:9b"
    chunk_size: int = 900
    chunk_overlap: int = 150


settings = Settings()
