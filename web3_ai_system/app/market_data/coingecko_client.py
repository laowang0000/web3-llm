import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv


DEFAULT_COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
DEFAULT_TIMEOUT_SECONDS = 10.0
SYMBOL_TO_COIN_ID = {
    "BTC": "bitcoin",
    "BTCUSDT": "bitcoin",
    "ETH": "ethereum",
    "ETHUSDT": "ethereum",
    "SOL": "solana",
    "SOLUSDT": "solana",
    "MATIC": "polygon",
    "MATICUSDT": "polygon",
    "POL": "polygon-ecosystem-token",
    "POLUSDT": "polygon-ecosystem-token",
    "BNB": "binancecoin",
    "BNBUSDT": "binancecoin",
    "XRP": "ripple",
    "XRPUSDT": "ripple",
    "ADA": "cardano",
    "ADAUSDT": "cardano",
    "DOGE": "dogecoin",
    "DOGEUSDT": "dogecoin",
    "AVAX": "avalanche-2",
    "AVAXUSDT": "avalanche-2",
    "LINK": "chainlink",
    "LINKUSDT": "chainlink",
    "DOT": "polkadot",
    "DOTUSDT": "polkadot",
    "TRX": "tron",
    "TRXUSDT": "tron",
    "LTC": "litecoin",
    "LTCUSDT": "litecoin",
    "BCH": "bitcoin-cash",
    "BCHUSDT": "bitcoin-cash",
    "UNI": "uniswap",
    "UNIUSDT": "uniswap",
    "AAVE": "aave",
    "AAVEUSDT": "aave",
    "ARB": "arbitrum",
    "ARBUSDT": "arbitrum",
    "OP": "optimism",
    "OPUSDT": "optimism",
}
COIN_ID_FALLBACKS = {
    "polygon-ecosystem-token": ["polygon"],
}


class CoinGeckoClientError(RuntimeError):
    """Raised when CoinGecko public market data cannot be fetched."""


@dataclass(frozen=True)
class CoinGeckoSettings:
    base_url: str
    timeout_seconds: float
    api_key: str | None = None


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_coingecko_settings() -> CoinGeckoSettings:
    _load_environment()
    return CoinGeckoSettings(
        base_url=os.getenv("COINGECKO_BASE_URL", DEFAULT_COINGECKO_BASE_URL).rstrip("/"),
        timeout_seconds=float(
            os.getenv("MARKET_REQUEST_TIMEOUT")
            or os.getenv("MARKET_TIMEOUT_SECONDS")
            or str(DEFAULT_TIMEOUT_SECONDS)
        ),
        api_key=_optional_api_key(os.getenv("COINGECKO_API_KEY")),
    )


class CoinGeckoClient:
    """Read-only client for CoinGecko public market endpoints."""

    def __init__(self, settings: CoinGeckoSettings | None = None) -> None:
        self.settings = settings or get_coingecko_settings()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.settings.base_url}{path}"
        headers = {}
        if self.settings.api_key:
            headers["x-cg-demo-api-key"] = self.settings.api_key
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise CoinGeckoClientError("CoinGecko request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise CoinGeckoClientError(f"CoinGecko returned HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise CoinGeckoClientError(f"Could not connect to CoinGecko: {exc}") from exc
        except ValueError as exc:
            raise CoinGeckoClientError("CoinGecko returned invalid JSON.") from exc

    def resolve_coin_id(self, symbol: str) -> str:
        normalized_symbol = symbol.strip().upper()
        coin_id = SYMBOL_TO_COIN_ID.get(normalized_symbol)
        if coin_id is None:
            raise CoinGeckoClientError(f"Unsupported CoinGecko symbol: {symbol}")
        return coin_id

    def _candidate_coin_ids(self, symbol: str) -> list[str]:
        coin_id = self.resolve_coin_id(symbol)
        return [coin_id, *COIN_ID_FALLBACKS.get(coin_id, [])]

    def fetch_market_snapshot(self, symbol: str, vs_currency: str = "usd") -> dict[str, Any]:
        normalized_symbol = _base_symbol(symbol)
        payload: dict[str, Any] | None = None
        coin_data: dict[str, Any] | None = None
        selected_coin_id: str | None = None
        for coin_id in self._candidate_coin_ids(normalized_symbol):
            payload = self._get(
                "/simple/price",
                {
                    "ids": coin_id,
                    "vs_currencies": vs_currency,
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                    "include_24hr_change": "true",
                    "include_last_updated_at": "true",
                },
            )
            coin_data = payload.get(coin_id)
            if coin_data:
                selected_coin_id = coin_id
                break
        if not coin_data or not selected_coin_id:
            raise CoinGeckoClientError(f"No CoinGecko data returned for {normalized_symbol}.")

        return {
            "symbol": normalized_symbol,
            "provider": "coingecko",
            "price_usd": _optional_float(coin_data.get(vs_currency)),
            "market_cap_usd": _optional_float(coin_data.get(f"{vs_currency}_market_cap")),
            "volume_24h_usd": _optional_float(coin_data.get(f"{vs_currency}_24h_vol")),
            "change_24h_percent": _optional_float(coin_data.get(f"{vs_currency}_24h_change")),
            "raw": payload or {},
            "source": "coingecko:/simple/price",
            "coin_id": selected_coin_id,
            "currency": vs_currency,
            "last_updated_at": coin_data.get("last_updated_at"),
        }

    def fetch_market_chart(self, symbol: str, vs_currency: str = "usd", days: int = 30) -> pd.DataFrame:
        normalized_symbol = _base_symbol(symbol)
        last_error: str | None = None
        for coin_id in self._candidate_coin_ids(normalized_symbol):
            try:
                payload = self._get(
                    f"/coins/{coin_id}/market_chart",
                    {
                        "vs_currency": vs_currency,
                        "days": str(days),
                    },
                )
            except CoinGeckoClientError as exc:
                last_error = str(exc)
                continue
            prices = payload.get("prices") or []
            volumes = payload.get("total_volumes") or []
            if not prices:
                last_error = f"No CoinGecko market chart prices returned for {coin_id}."
                continue
            frame = _market_chart_frame(prices=prices, volumes=volumes, symbol=normalized_symbol)
            if frame.empty:
                last_error = f"CoinGecko market chart for {coin_id} did not contain usable rows."
                continue
            frame.attrs["source"] = "coingecko:/coins/{id}/market_chart"
            frame.attrs["provider"] = "coingecko"
            frame.attrs["data_warning"] = (
                "CoinGecko market_chart provides historical price and volume series; "
                "open, high, and low are derived from adjacent sampled prices for indicator compatibility."
            )
            return frame
        raise CoinGeckoClientError(last_error or f"No CoinGecko market chart data returned for {normalized_symbol}.")


def _base_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("-", "").replace("/", "")
    return normalized[:-4] if normalized.endswith("USDT") else normalized


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_api_key(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned or cleaned == "PUT_MY_LOCAL_KEY_HERE":
        return None
    return cleaned


def _market_chart_frame(prices: list[Any], volumes: list[Any], symbol: str) -> pd.DataFrame:
    price_frame = pd.DataFrame(prices, columns=["timestamp_ms", "close"])
    volume_frame = pd.DataFrame(volumes, columns=["timestamp_ms", "volume"])
    frame = price_frame.merge(volume_frame, on="timestamp_ms", how="left")
    frame["timestamp"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True, errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "close"]).sort_values("timestamp").reset_index(drop=True)
    if frame.empty:
        return frame
    frame["volume"] = frame["volume"].fillna(0.0)
    frame["open"] = frame["close"].shift(1).fillna(frame["close"])
    frame["high"] = frame[["open", "close"]].max(axis=1)
    frame["low"] = frame[["open", "close"]].min(axis=1)
    frame["symbol"] = f"{symbol}USDT"
    return frame[["timestamp", "symbol", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
