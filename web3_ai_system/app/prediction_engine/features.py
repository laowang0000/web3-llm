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
