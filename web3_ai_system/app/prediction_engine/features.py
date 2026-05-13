import pandas as pd


def compute_rsi(price_series: pd.Series, window: int = 14) -> pd.Series:
    delta = price_series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = losses.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def compute_bollinger_bands(
    price_series: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    middle = price_series.rolling(window=window, min_periods=window).mean()
    std = price_series.rolling(window=window, min_periods=window).std()
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    return upper, middle, lower


def build_indicator_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Build technical indicators from real OHLCV candles.

    Expected columns: timestamp, open, high, low, close, volume.
    """
    required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")

    indicators = frame.copy().sort_values("timestamp").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume"]:
        indicators[column] = pd.to_numeric(indicators[column], errors="coerce")
    indicators = indicators.dropna(subset=["open", "high", "low", "close", "volume"])
    if len(indicators) < 50:
        raise ValueError("At least 50 OHLCV candles are required for stable indicators.")

    indicators["rsi"] = compute_rsi(indicators["close"], window=14)
    indicators["ema_12"] = indicators["close"].ewm(span=12, adjust=False).mean()
    indicators["ema_20"] = indicators["close"].ewm(span=20, adjust=False).mean()
    indicators["ema_26"] = indicators["close"].ewm(span=26, adjust=False).mean()
    indicators["ema_50"] = indicators["close"].ewm(span=50, adjust=False).mean()
    indicators["macd"] = indicators["ema_12"] - indicators["ema_26"]
    indicators["macd_signal"] = indicators["macd"].ewm(span=9, adjust=False).mean()
    indicators["macd_histogram"] = indicators["macd"] - indicators["macd_signal"]

    upper, middle, lower = compute_bollinger_bands(indicators["close"], window=20)
    indicators["bollinger_upper"] = upper
    indicators["bollinger_middle"] = middle
    indicators["bollinger_lower"] = lower
    indicators["bollinger_bandwidth"] = (
        (indicators["bollinger_upper"] - indicators["bollinger_lower"])
        / indicators["bollinger_middle"]
    )

    indicators["return_1"] = indicators["close"].pct_change()
    indicators["volatility_20"] = indicators["return_1"].rolling(window=20, min_periods=20).std()
    return indicators.dropna().reset_index(drop=True)


def get_latest_indicator_snapshot(indicator_frame: pd.DataFrame) -> dict:
    if indicator_frame.empty:
        raise ValueError("Indicator frame is empty.")

    latest = indicator_frame.tail(1).iloc[0]
    return {
        "close": round(float(latest["close"]), 8),
        "rsi": round(float(latest["rsi"]), 2),
        "ema_12": round(float(latest["ema_12"]), 8),
        "ema_20": round(float(latest["ema_20"]), 8),
        "ema_26": round(float(latest["ema_26"]), 8),
        "ema_50": round(float(latest["ema_50"]), 8),
        "macd": round(float(latest["macd"]), 8),
        "macd_signal": round(float(latest["macd_signal"]), 8),
        "macd_histogram": round(float(latest["macd_histogram"]), 8),
        "bollinger_upper": round(float(latest["bollinger_upper"]), 8),
        "bollinger_middle": round(float(latest["bollinger_middle"]), 8),
        "bollinger_lower": round(float(latest["bollinger_lower"]), 8),
        "bollinger_bandwidth": round(float(latest["bollinger_bandwidth"]), 6),
        "volatility_20": round(float(latest["volatility_20"]), 6),
    }


def build_feature_frame(frame: pd.DataFrame, horizon_days: int = 1) -> pd.DataFrame:
    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1")

    features = frame.copy()
    features["return_1"] = features["price"].pct_change()
    features["return_3"] = features["price"].pct_change(periods=3)
    features["volume_change_1"] = features["volume"].pct_change()

    features["rsi"] = compute_rsi(features["price"], window=14)
    features["ema"] = features["price"].ewm(span=12, adjust=False).mean()
    features["ema_26"] = features["price"].ewm(span=26, adjust=False).mean()
    features["macd"] = features["ema"] - features["ema_26"]
    features["macd_signal"] = features["macd"].ewm(span=9, adjust=False).mean()
    features["macd_hist"] = features["macd"] - features["macd_signal"]

    features["future_price"] = features["price"].shift(-horizon_days)
    features["target"] = (features["future_price"] > features["price"]).astype(int)
    features["target_label"] = features["target"].map({1: "UP", 0: "DOWN"})

    model_frame = features.dropna().reset_index(drop=True)
    return model_frame


def get_feature_columns() -> list[str]:
    return [
        "price",
        "volume",
        "rsi",
        "ema",
        "macd",
        "return_1",
        "return_3",
        "volume_change_1",
        "macd_signal",
        "macd_hist",
    ]
