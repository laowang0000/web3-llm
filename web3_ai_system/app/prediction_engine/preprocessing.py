import pandas as pd


def validate_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    price_column = "price" if "price" in frame.columns else "close" if "close" in frame.columns else None
    required_columns = {"timestamp", "volume"}
    if price_column is None:
        required_columns.add("price")
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    cleaned = frame.copy()
    cleaned["timestamp"] = pd.to_datetime(cleaned["timestamp"], utc=True, errors="coerce")
    cleaned["price"] = pd.to_numeric(cleaned[price_column], errors="coerce")
    if "close" not in cleaned.columns:
        cleaned["close"] = cleaned["price"]
    else:
        cleaned["close"] = pd.to_numeric(cleaned["close"], errors="coerce")
    cleaned["volume"] = pd.to_numeric(cleaned["volume"], errors="coerce")
    cleaned = cleaned.dropna(subset=["timestamp", "price", "close", "volume"])
    cleaned = cleaned.sort_values("timestamp").reset_index(drop=True)
    return cleaned
