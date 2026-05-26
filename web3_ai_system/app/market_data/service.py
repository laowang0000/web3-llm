from typing import Any

import pandas as pd

from app.market_data.binance_client import BinanceClient, BinanceClientError
from app.market_data.coingecko_client import CoinGeckoClient, CoinGeckoClientError
from app.prediction_engine.data_loader import build_demo_market_data
from app.prediction_engine.features import build_indicator_frame, get_latest_indicator_snapshot


class MarketDataServiceError(RuntimeError):
    """Raised when normalized market data cannot be produced."""


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("-", "").replace("/", "")
    if not normalized:
        raise MarketDataServiceError("Symbol is required.")
    if normalized in {"BTC", "ETH", "SOL", "MATIC"}:
        return f"{normalized}USDT"
    return normalized


class MarketDataService:
    def __init__(
        self,
        binance_client: BinanceClient | None = None,
        coingecko_client: CoinGeckoClient | None = None,
    ) -> None:
        self.binance = binance_client or BinanceClient()
        self.coingecko = coingecko_client or CoinGeckoClient()

    def get_market_snapshot(self, symbol: str) -> tuple[dict[str, Any], list[str]]:
        normalized_symbol = normalize_symbol(symbol)
        sources: list[str] = []

        binance_data: dict[str, Any] | None = None
        coingecko_data: dict[str, Any] | None = None
        errors: list[str] = []

        try:
            binance_data = self.binance.fetch_realtime_price(normalized_symbol)
            sources.append(binance_data["source"])
        except BinanceClientError as exc:
            errors.append(str(exc))

        try:
            coingecko_data = self.coingecko.fetch_market_snapshot(normalized_symbol)
            sources.append(coingecko_data["source"])
        except CoinGeckoClientError as exc:
            errors.append(str(exc))

        if binance_data is None and coingecko_data is None:
            snapshot = self._demo_market_snapshot(normalized_symbol, errors)
            return snapshot, ["backend-demo:/market-snapshot"]

        price = None
        if binance_data is not None:
            price = binance_data["price"]
        elif coingecko_data is not None:
            price = coingecko_data["price"]

        snapshot = {
            "symbol": normalized_symbol,
            "price": price,
            "binance": binance_data,
            "coingecko": coingecko_data,
            "market_cap": coingecko_data.get("market_cap") if coingecko_data else None,
            "volume_24h": coingecko_data.get("volume_24h") if coingecko_data else None,
            "change_24h_percent": coingecko_data.get("change_24h_percent") if coingecko_data else None,
            "source_warnings": errors,
        }
        return snapshot, sources

    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 120) -> tuple[pd.DataFrame, list[str]]:
        normalized_symbol = normalize_symbol(symbol)
        try:
            frame = self.binance.fetch_ohlcv(normalized_symbol, interval=timeframe, limit=limit)
        except BinanceClientError as exc:
            frame = self._demo_ohlcv(normalized_symbol, timeframe=timeframe, limit=limit, reason=str(exc))
            return frame, ["backend-demo:/ohlcv"]
        return frame, ["binance:/api/v3/klines"]

    def analyze_basic(self, symbol: str, timeframe: str = "1h", limit: int = 120) -> tuple[dict[str, Any], list[str]]:
        normalized_symbol = normalize_symbol(symbol)
        market_snapshot, market_sources = self.get_market_snapshot(normalized_symbol)
        ohlcv_frame, candle_sources = self.get_ohlcv(normalized_symbol, timeframe=timeframe, limit=limit)
        source_warnings = list(market_snapshot.get("source_warnings", []))
        data_mode = market_snapshot.get("data_mode", "live")
        if any(source.startswith("backend-demo:") for source in candle_sources):
            data_mode = "backend_demo_fallback"
            fallback_reason = ohlcv_frame.attrs.get("fallback_reason")
            warning = "Live Binance candle data was unavailable. Backend returned deterministic academic demo OHLCV data."
            if fallback_reason:
                warning = f"{warning} Reason: {fallback_reason}"
            source_warnings.append(warning)

        indicator_frame = build_indicator_frame(ohlcv_frame)
        indicators = get_latest_indicator_snapshot(indicator_frame)
        trend = self._summarize_trend(indicators)
        risk_flags = self._build_risk_flags(indicators)

        data = {
            "symbol": normalized_symbol,
            "timeframe": timeframe,
            "price": market_snapshot["price"],
            "indicators": indicators,
            "trend": trend,
            "risk_flags": risk_flags,
            "latest_candle": self._latest_candle(ohlcv_frame),
            "market": {
                "market_cap": market_snapshot.get("market_cap"),
                "volume_24h": market_snapshot.get("volume_24h"),
                "change_24h_percent": market_snapshot.get("change_24h_percent"),
            },
            "source_warnings": source_warnings,
            "data_mode": data_mode,
        }
        return data, list(dict.fromkeys(market_sources + candle_sources))

    def _demo_market_snapshot(self, symbol: str, errors: list[str]) -> dict[str, Any]:
        demo_frame = self._demo_ohlcv(symbol, timeframe="1h", limit=120, reason="; ".join(errors))
        latest = demo_frame.tail(1).iloc[0]
        previous = demo_frame.tail(25).iloc[0]
        price = round(float(latest["close"]), 8)
        volume_24h = round(float(demo_frame.tail(24)["volume"].sum()), 2)
        change_24h = round(((float(latest["close"]) - float(previous["close"])) / float(previous["close"])) * 100, 4)
        return {
            "symbol": symbol,
            "price": price,
            "binance": None,
            "coingecko": None,
            "market_cap": round(price * 19_700_000, 2) if symbol.startswith("BTC") else None,
            "volume_24h": volume_24h,
            "change_24h_percent": change_24h,
            "source_warnings": [
                "Live market providers were unavailable. Backend returned deterministic academic demo market data.",
                *errors,
            ],
            "data_mode": "backend_demo_fallback",
        }

    def _demo_ohlcv(self, symbol: str, timeframe: str, limit: int, reason: str) -> pd.DataFrame:
        periods = max(limit, 120)
        base_frame = build_demo_market_data(periods=periods).tail(limit).reset_index(drop=True)
        scale = {
            "BTCUSDT": 640.0,
            "ETHUSDT": 32.0,
            "SOLUSDT": 1.45,
            "MATICUSDT": 0.008,
        }.get(symbol, 10.0)
        close = base_frame["price"] * scale
        open_price = close.shift(1).fillna(close.iloc[0] * 0.996)
        spread = close * 0.006
        demo = pd.DataFrame(
            {
                "timestamp": self._demo_timestamps(limit, timeframe),
                "open": open_price.round(8),
                "high": pd.concat([open_price, close], axis=1).max(axis=1).add(spread).round(8),
                "low": pd.concat([open_price, close], axis=1).min(axis=1).sub(spread).round(8),
                "close": close.round(8),
                "volume": (base_frame["volume"] * max(scale / 10, 1)).round(8),
            }
        )
        demo.attrs["fallback_reason"] = reason
        return demo

    def _demo_timestamps(self, limit: int, timeframe: str) -> pd.DatetimeIndex:
        frequency = {
            "15m": "15min",
            "1h": "h",
            "4h": "4h",
            "1d": "D",
        }.get(timeframe, "h")
        return pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("min"), periods=limit, freq=frequency)

    def _latest_candle(self, frame: pd.DataFrame) -> dict[str, Any]:
        latest = frame.tail(1).iloc[0]
        return {
            "timestamp": latest["timestamp"].isoformat(),
            "open": round(float(latest["open"]), 8),
            "high": round(float(latest["high"]), 8),
            "low": round(float(latest["low"]), 8),
            "close": round(float(latest["close"]), 8),
            "volume": round(float(latest["volume"]), 8),
        }

    def _summarize_trend(self, indicators: dict[str, Any]) -> str:
        score = 0
        if indicators["close"] > indicators["ema_20"]:
            score += 1
        else:
            score -= 1
        if indicators["ema_20"] > indicators["ema_50"]:
            score += 1
        else:
            score -= 1
        if indicators["macd_histogram"] > 0:
            score += 1
        else:
            score -= 1
        if indicators["rsi"] > 60:
            score += 1
        elif indicators["rsi"] < 40:
            score -= 1

        if score >= 3:
            return "Bullish momentum: price is above key EMAs and MACD momentum is positive."
        if score <= -3:
            return "Bearish momentum: price is below key EMAs and MACD momentum is negative."
        return "Mixed or neutral momentum: indicators do not strongly agree."

    def _build_risk_flags(self, indicators: dict[str, Any]) -> list[str]:
        flags: list[str] = []
        if indicators["rsi"] >= 70:
            flags.append("RSI is overbought; upside may be stretched.")
        elif indicators["rsi"] <= 30:
            flags.append("RSI is oversold; downside may be stretched.")

        if indicators["close"] >= indicators["bollinger_upper"]:
            flags.append("Price is near or above the upper Bollinger Band.")
        elif indicators["close"] <= indicators["bollinger_lower"]:
            flags.append("Price is near or below the lower Bollinger Band.")

        if indicators["volatility_20"] >= 0.04:
            flags.append("Recent 20-candle volatility is elevated.")
        if indicators["bollinger_bandwidth"] >= 0.08:
            flags.append("Bollinger Bandwidth is wide; market movement may be unstable.")
        if not flags:
            flags.append("No major technical risk flag detected from the selected timeframe.")
        return flags
