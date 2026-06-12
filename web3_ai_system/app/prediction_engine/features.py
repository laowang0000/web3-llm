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
    indicators["ema_200"] = indicators["close"].ewm(span=200, adjust=False).mean()
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
    indicators["support_20"] = indicators["low"].rolling(window=20, min_periods=20).min()
    indicators["resistance_20"] = indicators["high"].rolling(window=20, min_periods=20).max()
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
        "ema_200": round(float(latest["ema_200"]), 8),
        "macd": round(float(latest["macd"]), 8),
        "macd_signal": round(float(latest["macd_signal"]), 8),
        "macd_histogram": round(float(latest["macd_histogram"]), 8),
        "bollinger_upper": round(float(latest["bollinger_upper"]), 8),
        "bollinger_middle": round(float(latest["bollinger_middle"]), 8),
        "bollinger_lower": round(float(latest["bollinger_lower"]), 8),
        "bollinger_bandwidth": round(float(latest["bollinger_bandwidth"]), 6),
        "volatility_20": round(float(latest["volatility_20"]), 6),
        "support_20": round(float(latest["support_20"]), 8),
        "resistance_20": round(float(latest["resistance_20"]), 8),
    }


def build_feature_frame(
    frame: pd.DataFrame,
    horizon_candles: int = 1,
    horizon_days: int | None = None,
) -> pd.DataFrame:
    if horizon_days is not None:
        horizon_candles = horizon_days
    if horizon_candles < 1:
        raise ValueError("horizon_candles must be at least 1")

    features = frame.copy().sort_values("timestamp").reset_index(drop=True)
    if "close" not in features.columns and "price" in features.columns:
        features["close"] = features["price"]
    if "price" not in features.columns and "close" in features.columns:
        features["price"] = features["close"]
    if "close" not in features.columns:
        raise ValueError("Feature frame requires either close or price.")

    for column in ["open", "high", "low", "close", "price", "volume"]:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")

    features["return_1"] = features["close"].pct_change()
    features["return_lag_1"] = features["return_1"].shift(1)
    features["return_lag_2"] = features["return_1"].shift(2)
    features["return_lag_3"] = features["return_1"].shift(3)
    features["rolling_mean_return_5"] = features["return_1"].rolling(window=5, min_periods=5).mean()
    features["rolling_mean_return_10"] = features["return_1"].rolling(window=10, min_periods=10).mean()
    features["momentum_3"] = features["close"].pct_change(periods=3)
    features["momentum_5"] = features["close"].pct_change(periods=5)
    features["momentum_10"] = features["close"].pct_change(periods=10)
    features["volume_change"] = features["volume"].pct_change()

    if "rsi" not in features.columns:
        features["rsi"] = compute_rsi(features["close"], window=14)
    if "ema_12" not in features.columns:
        features["ema_12"] = features["close"].ewm(span=12, adjust=False).mean()
    features["ema"] = features["ema_12"]
    if "ema_20" not in features.columns:
        features["ema_20"] = features["close"].ewm(span=20, adjust=False).mean()
    if "ema_26" not in features.columns:
        features["ema_26"] = features["close"].ewm(span=26, adjust=False).mean()
    if "ema_50" not in features.columns:
        features["ema_50"] = features["close"].ewm(span=50, adjust=False).mean()
    if "ema_200" not in features.columns:
        features["ema_200"] = features["close"].ewm(span=200, adjust=False).mean()
    features["ema_short"] = features["ema_12"]
    features["ema_long"] = features["ema_50"]
    features["ema_distance"] = (features["ema_short"] - features["ema_long"]) / features["close"]
    features["close_to_ema_short"] = (features["close"] - features["ema_short"]) / features["close"]
    features["close_to_ema_long"] = (features["close"] - features["ema_long"]) / features["close"]
    if "macd" not in features.columns:
        features["macd"] = features["ema_12"] - features["ema_26"]
    if "macd_signal" not in features.columns:
        features["macd_signal"] = features["macd"].ewm(span=9, adjust=False).mean()
    if "macd_histogram" not in features.columns:
        features["macd_histogram"] = features["macd"] - features["macd_signal"]
    features["macd_hist"] = features["macd_histogram"]

    if "bollinger_bandwidth" not in features.columns:
        upper, middle, lower = compute_bollinger_bands(features["close"], window=20)
        features["bollinger_upper"] = upper
        features["bollinger_middle"] = middle
        features["bollinger_lower"] = lower
        features["bollinger_bandwidth"] = (
            (features["bollinger_upper"] - features["bollinger_lower"])
            / features["bollinger_middle"]
        )
    if "volatility_20" not in features.columns:
        features["volatility_20"] = features["return_1"].rolling(window=20, min_periods=20).std()
    features["rolling_volatility_10"] = features["return_1"].rolling(window=10, min_periods=10).std()

    if {"high", "low"}.issubset(features.columns):
        previous_close = features["close"].shift(1)
        true_range = pd.concat(
            [
                features["high"] - features["low"],
                (features["high"] - previous_close).abs(),
                (features["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        features["atr_14"] = true_range.rolling(window=14, min_periods=14).mean()
        features["atr_14_pct"] = features["atr_14"] / features["close"]
    else:
        features["atr_14_pct"] = features["volatility_20"]

    features["trend_strength_proxy"] = (
        features["ema_distance"].abs()
        + (features["macd_histogram"].abs() / features["close"])
        + features["rolling_volatility_10"].fillna(0)
    )

    features["target_future_close"] = features["close"].shift(-horizon_candles)
    features = features.dropna(subset=["target_future_close"]).copy()
    features["target"] = (features["target_future_close"] > features["close"]).astype(int)
    features["target_label"] = features["target"].map({1: "UP", 0: "DOWN"})

    model_frame = features.dropna().reset_index(drop=True)
    return model_frame


def get_feature_columns() -> list[str]:
    return [
        "close",
        "volume",
        "rsi",
        "ema_short",
        "ema_long",
        "ema_distance",
        "close_to_ema_short",
        "close_to_ema_long",
        "macd",
        "macd_signal",
        "macd_histogram",
        "bollinger_bandwidth",
        "volatility_20",
        "rolling_volatility_10",
        "return_1",
        "rolling_mean_return_5",
        "rolling_mean_return_10",
        "return_lag_1",
        "return_lag_2",
        "return_lag_3",
        "volume_change",
        "momentum_3",
        "momentum_5",
        "momentum_10",
        "atr_14_pct",
        "trend_strength_proxy",
    ]
