import pandas as pd


def validate_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"timestamp", "price", "volume"}
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    cleaned = frame.copy()
    cleaned["timestamp"] = pd.to_datetime(cleaned["timestamp"], utc=True, errors="coerce")
    cleaned["price"] = pd.to_numeric(cleaned["price"], errors="coerce")
    cleaned["volume"] = pd.to_numeric(cleaned["volume"], errors="coerce")
    cleaned = cleaned.dropna(subset=["timestamp", "price", "volume"])
    cleaned = cleaned.sort_values("timestamp").reset_index(drop=True)
    return cleaned
