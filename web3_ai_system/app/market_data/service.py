from datetime import datetime, timezone
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from app.market_data.binance_client import BinanceClient, BinanceClientError
from app.market_data.coingecko_client import CoinGeckoClient, CoinGeckoClientError
from app.market_data.coinpaprika_client import CoinPaprikaClient, CoinPaprikaClientError
from app.prediction_engine.features import build_indicator_frame, get_latest_indicator_snapshot


DEFAULT_PROVIDER_ORDER = ["binance", "coingecko", "coinpaprika"]
SUPPORTED_PROVIDERS = set(DEFAULT_PROVIDER_ORDER)
SUPPORTED_BASE_SYMBOLS = {
    "BTC",
    "ETH",
    "SOL",
    "MATIC",
    "POL",
    "BNB",
    "XRP",
    "ADA",
    "DOGE",
    "AVAX",
    "LINK",
    "DOT",
    "TRX",
    "LTC",
    "BCH",
    "UNI",
    "AAVE",
    "ARB",
    "OP",
}


class MarketDataServiceError(RuntimeError):
    """Raised when normalized market data cannot be produced."""


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("-", "").replace("/", "")
    if not normalized:
        raise MarketDataServiceError("Symbol is required.")
    base = normalized[:-4] if normalized.endswith("USDT") else normalized
    if base not in SUPPORTED_BASE_SYMBOLS:
        supported = ", ".join(sorted(SUPPORTED_BASE_SYMBOLS))
        raise MarketDataServiceError(f"Unsupported market symbol: {symbol}. Supported symbols: {supported}.")
    return f"{base}USDT"


def base_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    return normalized[:-4] if normalized.endswith("USDT") else normalized


def get_provider_order() -> list[str]:
    _load_environment()
    configured = os.getenv("MARKET_PROVIDER_ORDER", ",".join(DEFAULT_PROVIDER_ORDER))
    providers = [provider.strip().lower() for provider in configured.split(",") if provider.strip()]
    valid = [provider for provider in providers if provider in SUPPORTED_PROVIDERS]
    return valid or list(DEFAULT_PROVIDER_ORDER)


class MarketDataService:
    def __init__(
        self,
        binance_client: BinanceClient | None = None,
        coingecko_client: CoinGeckoClient | None = None,
        coinpaprika_client: CoinPaprikaClient | None = None,
    ) -> None:
        self.binance = binance_client or BinanceClient()
        self.coingecko = coingecko_client or CoinGeckoClient()
        self.coinpaprika = coinpaprika_client or CoinPaprikaClient()

    def get_market_snapshot(self, symbol: str) -> tuple[dict[str, Any], list[str]]:
        normalized_symbol = normalize_symbol(symbol)
        provider_errors: list[str] = []

        for provider in get_provider_order():
            try:
                snapshot = self._fetch_snapshot_from_provider(provider, normalized_symbol)
                snapshot = self._normalize_snapshot(snapshot, normalized_symbol, provider_errors)
                return snapshot, [snapshot["source"]]
            except (BinanceClientError, CoinGeckoClientError, CoinPaprikaClientError, MarketDataServiceError) as exc:
                error_summary = f"{provider}: {exc}"
                provider_errors.append(error_summary)
                print(f"[market_data] Provider failed for {normalized_symbol}: {error_summary}")

        raise MarketDataServiceError(
            f"All market data providers failed for {base_symbol(normalized_symbol)}. "
            f"Provider errors: {' | '.join(provider_errors)}"
        )

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 120,
        provider_order: list[str] | None = None,
        skip_providers: set[str] | None = None,
    ) -> tuple[pd.DataFrame, list[str]]:
        normalized_symbol = normalize_symbol(symbol)
        provider_errors: list[str] = []
        skipped = skip_providers or set()
        order = [provider for provider in (provider_order or get_provider_order()) if provider not in skipped]

        for provider in order:
            if provider == "binance":
                try:
                    frame = self.binance.fetch_ohlcv(normalized_symbol, interval=timeframe, limit=limit)
                    return frame, ["binance:/api/v3/klines"]
                except BinanceClientError as exc:
                    error_summary = f"binance: {exc}"
                    provider_errors.append(error_summary)
                    print(f"[market_data] Historical provider failed for {normalized_symbol}: {error_summary}")
                continue

            if provider == "coingecko":
                try:
                    days = min(self._coingecko_chart_days(timeframe=timeframe, limit=limit), 365)
                    frame = self.coingecko.fetch_market_chart(base_symbol(normalized_symbol), days=days)
                    if len(frame) < 50:
                        raise MarketDataServiceError(
                            f"CoinGecko historical fallback returned only {len(frame)} usable rows."
                        )
                    return frame.tail(limit).reset_index(drop=True), ["coingecko:/coins/{id}/market_chart"]
                except (CoinGeckoClientError, MarketDataServiceError) as exc:
                    error_summary = f"coingecko: {exc}"
                    provider_errors.append(error_summary)
                    print(f"[market_data] Historical provider failed for {normalized_symbol}: {error_summary}")
                continue

            if provider == "coinpaprika":
                try:
                    days = min(max(limit, 90), 364)
                    frame = self.coinpaprika.fetch_market_chart(base_symbol(normalized_symbol), days=days)
                    if len(frame) < 50:
                        raise MarketDataServiceError(
                            f"CoinPaprika historical fallback returned only {len(frame)} usable rows."
                        )
                    return frame.tail(limit).reset_index(drop=True), ["coinpaprika:/tickers/{coin_id}/historical"]
                except (CoinPaprikaClientError, MarketDataServiceError) as exc:
                    error_summary = f"coinpaprika: {exc}"
                    provider_errors.append(error_summary)
                    print(f"[market_data] Historical provider failed for {normalized_symbol}: {error_summary}")
                continue

        raise MarketDataServiceError(
            "Prediction requires historical OHLCV data. Historical fallback providers did not return usable series. "
            f"Provider errors: {' | '.join(provider_errors)}"
        )

    def analyze_basic(self, symbol: str, timeframe: str = "1h", limit: int = 120) -> tuple[dict[str, Any], list[str]]:
        normalized_symbol = normalize_symbol(symbol)
        market_snapshot, market_sources = self.get_market_snapshot(normalized_symbol)
        source_warnings = list(market_snapshot.get("source_warnings", []))
        failed_snapshot_providers = _failed_providers_from_warnings(source_warnings)
        ohlcv_order = _prioritize_provider(get_provider_order(), market_snapshot["provider"])
        ohlcv_frame, candle_sources = self.get_ohlcv(
            normalized_symbol,
            timeframe=timeframe,
            limit=limit,
            provider_order=ohlcv_order,
            skip_providers=failed_snapshot_providers,
        )
        data_warning = ohlcv_frame.attrs.get("data_warning")
        if data_warning:
            source_warnings.append(data_warning)

        indicator_frame = build_indicator_frame(ohlcv_frame)
        indicators = get_latest_indicator_snapshot(indicator_frame)
        trend = self._summarize_trend(indicators)
        risk_flags = self._build_risk_flags(indicators)

        data = {
            "symbol": normalized_symbol,
            "provider": market_snapshot["provider"],
            "source": market_snapshot["source"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timeframe": timeframe,
            "price": market_snapshot["price_usd"],
            "price_usd": market_snapshot["price_usd"],
            "indicators": indicators,
            "trend": trend,
            "risk_flags": risk_flags,
            "latest_candle": self._latest_candle(ohlcv_frame),
            "market": {
                "provider": market_snapshot["provider"],
                "price_usd": market_snapshot["price_usd"],
                "market_cap_usd": market_snapshot["market_cap_usd"],
                "volume_24h_usd": market_snapshot["volume_24h_usd"],
                "change_24h_percent": market_snapshot["change_24h_percent"],
                "market_cap": market_snapshot["market_cap_usd"],
                "volume_24h": market_snapshot["volume_24h_usd"],
            },
            "source_warnings": source_warnings,
            "data_mode": "live",
        }
        return data, list(dict.fromkeys(market_sources + candle_sources))

    def _fetch_snapshot_from_provider(self, provider: str, symbol: str) -> dict[str, Any]:
        if provider == "binance":
            return self.binance.fetch_market_snapshot(symbol)
        if provider == "coingecko":
            return self.coingecko.fetch_market_snapshot(base_symbol(symbol))
        if provider == "coinpaprika":
            return self.coinpaprika.fetch_market_snapshot(base_symbol(symbol))
        raise MarketDataServiceError(f"Unsupported market provider: {provider}")

    def _normalize_snapshot(
        self,
        snapshot: dict[str, Any],
        requested_symbol: str,
        provider_errors: list[str],
    ) -> dict[str, Any]:
        provider = str(snapshot.get("provider") or "").strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise MarketDataServiceError(f"Provider returned unsupported provider value: {provider!r}")

        price_usd = _optional_float(snapshot.get("price_usd"))
        if price_usd is None:
            raise MarketDataServiceError(f"{provider} returned no USD price for {requested_symbol}.")

        normalized = {
            "symbol": base_symbol(requested_symbol),
            "trading_pair": normalize_symbol(requested_symbol),
            "provider": provider,
            "price_usd": price_usd,
            "market_cap_usd": _optional_float(snapshot.get("market_cap_usd")),
            "volume_24h_usd": _optional_float(snapshot.get("volume_24h_usd")),
            "change_24h_percent": _optional_float(snapshot.get("change_24h_percent")),
            "raw": snapshot.get("raw") or {},
            "source": snapshot.get("source") or f"{provider}:market-snapshot",
            "source_warnings": list(provider_errors),
            "data_mode": "live",
        }
        normalized["price"] = normalized["price_usd"]
        normalized["market_cap"] = normalized["market_cap_usd"]
        normalized["volume_24h"] = normalized["volume_24h_usd"]
        return normalized

    def _coingecko_chart_days(self, timeframe: str, limit: int) -> int:
        minutes_per_candle = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "6h": 360,
            "8h": 480,
            "12h": 720,
            "1d": 1440,
            "3d": 4320,
            "1w": 10080,
        }.get(timeframe, 60)
        return max(1, math.ceil((minutes_per_candle * limit) / 1440))

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


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _prioritize_provider(order: list[str], provider: str | None) -> list[str]:
    selected = (provider or "").strip().lower()
    if selected not in SUPPORTED_PROVIDERS:
        return order
    return [selected, *[item for item in order if item != selected]]


def _failed_providers_from_warnings(warnings: list[str]) -> set[str]:
    failed: set[str] = set()
    for warning in warnings:
        provider = warning.split(":", 1)[0].strip().lower()
        if provider in SUPPORTED_PROVIDERS:
            failed.add(provider)
    return failed
