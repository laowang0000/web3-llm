import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv


DEFAULT_BINANCE_BASE_URL = "https://api.binance.com"
DEFAULT_TIMEOUT_SECONDS = 10.0
SUPPORTED_INTERVALS = {
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
}


class BinanceClientError(RuntimeError):
    """Raised when Binance public market data cannot be fetched."""


@dataclass(frozen=True)
class BinanceSettings:
    base_url: str
    timeout_seconds: float


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_binance_settings() -> BinanceSettings:
    _load_environment()
    return BinanceSettings(
        base_url=os.getenv("BINANCE_BASE_URL", DEFAULT_BINANCE_BASE_URL).rstrip("/"),
        timeout_seconds=float(os.getenv("MARKET_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
    )


class BinanceClient:
    """Read-only client for Binance public spot market endpoints."""

    def __init__(self, settings: BinanceSettings | None = None) -> None:
        self.settings = settings or get_binance_settings()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.settings.base_url}{path}"
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise BinanceClientError("Binance request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise BinanceClientError(f"Binance returned HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise BinanceClientError(f"Could not connect to Binance: {exc}") from exc
        except ValueError as exc:
            raise BinanceClientError("Binance returned invalid JSON.") from exc

    def fetch_realtime_price(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = symbol.strip().upper()
        payload = self._get("/api/v3/ticker/price", {"symbol": normalized_symbol})
        return {
            "symbol": payload["symbol"],
            "price": float(payload["price"]),
            "source": "binance:/api/v3/ticker/price",
        }

    def fetch_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 120) -> pd.DataFrame:
        normalized_symbol = symbol.strip().upper()
        if interval not in SUPPORTED_INTERVALS:
            raise BinanceClientError(f"Unsupported Binance interval: {interval}")
        if not 1 <= limit <= 1000:
            raise BinanceClientError("Binance kline limit must be between 1 and 1000.")

        rows = self._get(
            "/api/v3/klines",
            {
                "symbol": normalized_symbol,
                "interval": interval,
                "limit": limit,
            },
        )
        if not isinstance(rows, list):
            raise BinanceClientError("Unexpected Binance kline response format.")

        frame = pd.DataFrame(
            rows,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base_asset_volume",
                "taker_buy_quote_asset_volume",
                "ignore",
            ],
        )
        if frame.empty:
            raise BinanceClientError(f"No OHLCV data returned for {normalized_symbol}.")

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_asset_volume",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
        ]
        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
        frame["symbol"] = normalized_symbol
        frame = frame.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
        return frame[
            [
                "timestamp",
                "close_time",
                "symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_asset_volume",
                "number_of_trades",
            ]
        ].reset_index(drop=True)

