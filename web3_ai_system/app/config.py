from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Web3 AI System"
    default_asset: str = "BTC"
    default_horizon_days: int = 3
    max_retrieved_documents: int = 3
    base_dir: Path = Path(__file__).resolve().parent.parent
    insight_data_dir: Path = base_dir / "data" / "insight_sources"
    chroma_persist_dir: Path = base_dir / "storage" / "chroma_insight"
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4.1-mini"
    chunk_size: int = 900
    chunk_overlap: int = 150


settings = Settings()
