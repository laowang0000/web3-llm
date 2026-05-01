from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"timestamp", "price", "volume"}


def load_market_data(csv_path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path)
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return frame


def build_demo_market_data(periods: int = 240) -> pd.DataFrame:
    timestamps = pd.date_range("2025-01-01", periods=periods, freq="D", tz="UTC")
    price = []
    volume = []
    current_price = 100.0
    current_volume = 1000.0

    for step in range(periods):
        direction = 1 if step % 9 not in (4, 5, 6) else -1
        current_price += (0.8 + (step % 5) * 0.15) * direction
        current_volume += 15 + (step % 7) * 3 + (20 if direction > 0 else -10)
        price.append(round(current_price, 2))
        volume.append(round(max(current_volume, 100.0), 2))

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "price": price,
            "volume": volume,
        }
    )
