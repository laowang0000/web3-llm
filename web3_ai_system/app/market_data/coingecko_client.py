import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
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
    "MATIC": "matic-network",
    "MATICUSDT": "matic-network",
}


class CoinGeckoClientError(RuntimeError):
    """Raised when CoinGecko public market data cannot be fetched."""


@dataclass(frozen=True)
class CoinGeckoSettings:
    base_url: str
    timeout_seconds: float


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_coingecko_settings() -> CoinGeckoSettings:
    _load_environment()
    return CoinGeckoSettings(
        base_url=os.getenv("COINGECKO_BASE_URL", DEFAULT_COINGECKO_BASE_URL).rstrip("/"),
        timeout_seconds=float(os.getenv("MARKET_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
    )


class CoinGeckoClient:
    """Read-only client for CoinGecko public market endpoints."""

    def __init__(self, settings: CoinGeckoSettings | None = None) -> None:
        self.settings = settings or get_coingecko_settings()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.settings.base_url}{path}"
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.get(url, params=params)
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

    def fetch_market_snapshot(self, symbol: str, vs_currency: str = "usd") -> dict[str, Any]:
        normalized_symbol = symbol.strip().upper()
        coin_id = self.resolve_coin_id(normalized_symbol)
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
        if not coin_data:
            raise CoinGeckoClientError(f"No CoinGecko data returned for {coin_id}.")

        return {
            "symbol": normalized_symbol,
            "coin_id": coin_id,
            "currency": vs_currency,
            "price": coin_data.get(vs_currency),
            "market_cap": coin_data.get(f"{vs_currency}_market_cap"),
            "volume_24h": coin_data.get(f"{vs_currency}_24h_vol"),
            "change_24h_percent": coin_data.get(f"{vs_currency}_24h_change"),
            "last_updated_at": coin_data.get("last_updated_at"),
            "source": "coingecko:/simple/price",
        }
