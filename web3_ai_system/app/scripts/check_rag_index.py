import argparse
import sqlite3

from app.config import settings
from app.insight_engine.embeddings import get_embedding_settings


def _collection_name(provider: str, model: str) -> str:
    safe_model = "".join(character if character.isalnum() else "_" for character in model.lower())
    return f"crypto_insight_{provider}_{safe_model}"[:63]


def _count_embeddings(collection_name: str) -> int:
    sqlite_path = settings.chroma_persist_dir / "chroma.sqlite3"
    if not sqlite_path.exists():
        return 0

    with sqlite3.connect(sqlite_path) as connection:
        cursor = connection.cursor()
        row = cursor.execute(
            "select id from collections where name = ?",
            (collection_name,),
        ).fetchone()
        if row is None:
            return 0

        collection_id = row[0]
        segment_rows = cursor.execute(
            "select id from segments where collection = ?",
            (collection_id,),
        ).fetchall()
        segment_ids = [segment_row[0] for segment_row in segment_rows]
        if not segment_ids:
            return 0

        placeholders = ",".join("?" for _ in segment_ids)
        count = cursor.execute(
            f"select count(*) from embeddings where segment_id in ({placeholders})",
            segment_ids,
        ).fetchone()[0]
        return int(count or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a local Chroma RAG index already exists.")
    parser.add_argument("--quiet", action="store_true", help="Only use the exit code.")
    args = parser.parse_args()

    embedding_settings = get_embedding_settings()
    collection_name = _collection_name(embedding_settings.provider, embedding_settings.model)
    count = _count_embeddings(collection_name)

    if not args.quiet:
        print(f"RAG collection: {collection_name}")
        print(f"Chroma path: {settings.chroma_persist_dir}")
        print(f"Indexed chunks: {count}")

    return 0 if count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
