import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv


DEFAULT_COINPAPRIKA_BASE_URL = "https://api.coinpaprika.com/v1"
DEFAULT_TIMEOUT_SECONDS = 10.0
SYMBOL_TO_COIN_ID = {
    "BTC": "btc-bitcoin",
    "BTCUSDT": "btc-bitcoin",
    "ETH": "eth-ethereum",
    "ETHUSDT": "eth-ethereum",
    "SOL": "sol-solana",
    "SOLUSDT": "sol-solana",
    "MATIC": "matic-polygon",
    "MATICUSDT": "matic-polygon",
    "POL": "pol-polygon-ecosystem-token",
    "POLUSDT": "pol-polygon-ecosystem-token",
    "BNB": "bnb-binance-coin",
    "BNBUSDT": "bnb-binance-coin",
    "XRP": "xrp-xrp",
    "XRPUSDT": "xrp-xrp",
    "ADA": "ada-cardano",
    "ADAUSDT": "ada-cardano",
    "DOGE": "doge-dogecoin",
    "DOGEUSDT": "doge-dogecoin",
    "AVAX": "avax-avalanche",
    "AVAXUSDT": "avax-avalanche",
    "LINK": "link-chainlink",
    "LINKUSDT": "link-chainlink",
    "DOT": "dot-polkadot",
    "DOTUSDT": "dot-polkadot",
    "TRX": "trx-tron",
    "TRXUSDT": "trx-tron",
    "LTC": "ltc-litecoin",
    "LTCUSDT": "ltc-litecoin",
    "BCH": "bch-bitcoin-cash",
    "BCHUSDT": "bch-bitcoin-cash",
    "UNI": "uni-uniswap",
    "UNIUSDT": "uni-uniswap",
    "AAVE": "aave-aave",
    "AAVEUSDT": "aave-aave",
    "ARB": "arb-arbitrum",
    "ARBUSDT": "arb-arbitrum",
    "OP": "op-optimism",
    "OPUSDT": "op-optimism",
}
COIN_ID_FALLBACKS = {
    "pol-polygon-ecosystem-token": ["matic-polygon"],
}


class CoinPaprikaClientError(RuntimeError):
    """Raised when CoinPaprika public market data cannot be fetched."""


@dataclass(frozen=True)
class CoinPaprikaSettings:
    base_url: str
    timeout_seconds: float
    api_key: str | None = None


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_coinpaprika_settings() -> CoinPaprikaSettings:
    _load_environment()
    return CoinPaprikaSettings(
        base_url=os.getenv("COINPAPRIKA_BASE_URL", DEFAULT_COINPAPRIKA_BASE_URL).rstrip("/"),
        timeout_seconds=float(
            os.getenv("MARKET_REQUEST_TIMEOUT")
            or os.getenv("MARKET_TIMEOUT_SECONDS")
            or str(DEFAULT_TIMEOUT_SECONDS)
        ),
        api_key=_optional_api_key(os.getenv("COINPAPRIKA_API_KEY")),
    )


class CoinPaprikaClient:
    """Read-only client for CoinPaprika public ticker endpoints."""

    def __init__(self, settings: CoinPaprikaSettings | None = None) -> None:
        self.settings = settings or get_coinpaprika_settings()

    def _get(self, path: str) -> Any:
        url = f"{self.settings.base_url}{path}"
        headers = {}
        if self.settings.api_key:
            headers["Authorization"] = self.settings.api_key
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise CoinPaprikaClientError("CoinPaprika request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise CoinPaprikaClientError(
                f"CoinPaprika returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise CoinPaprikaClientError(f"Could not connect to CoinPaprika: {exc}") from exc
        except ValueError as exc:
            raise CoinPaprikaClientError("CoinPaprika returned invalid JSON.") from exc

    def resolve_coin_ids(self, symbol: str) -> list[str]:
        normalized_symbol = symbol.strip().upper()
        coin_id = SYMBOL_TO_COIN_ID.get(normalized_symbol)
        if coin_id is None:
            raise CoinPaprikaClientError(f"Unsupported CoinPaprika symbol: {symbol}")
        return [coin_id, *COIN_ID_FALLBACKS.get(coin_id, [])]

    def fetch_market_snapshot(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = _base_symbol(symbol)
        last_error: str | None = None
        for coin_id in self.resolve_coin_ids(normalized_symbol):
            try:
                payload = self._get(f"/tickers/{coin_id}")
            except CoinPaprikaClientError as exc:
                last_error = str(exc)
                continue
            quotes = payload.get("quotes") or {}
            usd = quotes.get("USD") or {}
            price = _optional_float(usd.get("price"))
            if price is None:
                last_error = f"No CoinPaprika USD ticker data returned for {coin_id}."
                continue
            return {
                "symbol": normalized_symbol,
                "provider": "coinpaprika",
                "price_usd": price,
                "market_cap_usd": _optional_float(usd.get("market_cap")),
                "volume_24h_usd": _optional_float(usd.get("volume_24h")),
                "change_24h_percent": _optional_float(usd.get("percent_change_24h")),
                "raw": payload,
                "source": f"coinpaprika:/tickers/{coin_id}",
                "coin_id": coin_id,
            }
        raise CoinPaprikaClientError(last_error or f"No CoinPaprika data returned for {normalized_symbol}.")

    def fetch_market_chart(self, symbol: str, days: int = 120) -> pd.DataFrame:
        normalized_symbol = _base_symbol(symbol)
        start = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=max(days, 1))).strftime("%Y-%m-%d")
        last_error: str | None = None
        for coin_id in self.resolve_coin_ids(normalized_symbol):
            try:
                payload = self._get(f"/tickers/{coin_id}/historical?start={start}&interval=1d")
            except CoinPaprikaClientError as exc:
                last_error = str(exc)
                continue
            if not isinstance(payload, list) or not payload:
                last_error = f"No CoinPaprika historical rows returned for {coin_id}."
                continue
            frame = _historical_frame(payload=payload, symbol=normalized_symbol)
            if frame.empty:
                last_error = f"CoinPaprika historical data for {coin_id} did not contain usable rows."
                continue
            frame.attrs["source"] = f"coinpaprika:/tickers/{coin_id}/historical"
            frame.attrs["provider"] = "coinpaprika"
            frame.attrs["data_warning"] = (
                "CoinPaprika historical fallback uses its public daily price and volume series; "
                "open, high, and low are derived from adjacent sampled prices for indicator compatibility."
            )
            return frame
        raise CoinPaprikaClientError(last_error or f"No CoinPaprika historical data returned for {normalized_symbol}.")


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


def _historical_frame(payload: list[dict[str, Any]], symbol: str) -> pd.DataFrame:
    frame = pd.DataFrame(payload)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame.get("timestamp"), utc=True, errors="coerce")
    frame["close"] = pd.to_numeric(frame.get("price"), errors="coerce")
    frame["volume"] = pd.to_numeric(frame.get("volume_24h"), errors="coerce")
    frame = frame.dropna(subset=["timestamp", "close"]).sort_values("timestamp").reset_index(drop=True)
    if frame.empty:
        return frame
    frame["volume"] = frame["volume"].fillna(0.0)
    frame["open"] = frame["close"].shift(1).fillna(frame["close"])
    frame["high"] = frame[["open", "close"]].max(axis=1)
    frame["low"] = frame[["open", "close"]].min(axis=1)
    frame["symbol"] = f"{symbol}USDT"
    return frame[["timestamp", "symbol", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
