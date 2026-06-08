from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from app.market_data.coingecko_client import CoinGeckoClient
from app.market_data.coinpaprika_client import CoinPaprikaClient


def _print_result(name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def _check_snapshot(name: str, fetcher: Callable[[str], dict], symbol: str) -> bool:
    try:
        data = fetcher(symbol)
    except Exception as exc:
        _print_result(name, False, str(exc))
        return False

    price = data.get("price_usd")
    provider = data.get("provider")
    ok = provider in {"coingecko", "coinpaprika"} and isinstance(price, (int, float)) and price > 0
    detail = f"provider={provider}; price_usd={price}"
    _print_result(name, ok, detail)
    return ok


def main() -> int:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()

    coingecko = CoinGeckoClient()
    coinpaprika = CoinPaprikaClient()
    checks = [
        _check_snapshot("CoinGecko BTC", coingecko.fetch_market_snapshot, "BTC"),
        _check_snapshot("CoinGecko ETH", coingecko.fetch_market_snapshot, "ETH"),
        _check_snapshot("CoinGecko SOL", coingecko.fetch_market_snapshot, "SOL"),
        _check_snapshot("CoinPaprika BTC", coinpaprika.fetch_market_snapshot, "BTC"),
        _check_snapshot("CoinPaprika ETH", coinpaprika.fetch_market_snapshot, "ETH"),
        _check_snapshot("CoinPaprika SOL", coinpaprika.fetch_market_snapshot, "SOL"),
    ]

    if all(checks):
        print("Market provider test completed successfully.")
        return 0
    print("Market provider test failed. Check the provider error above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
