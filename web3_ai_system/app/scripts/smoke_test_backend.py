import argparse
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from app.analysis.hybrid_service import HybridAnalysisService
from app.market_data.service import MarketDataService


def _print_result(name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def _request(client: httpx.Client, method: str, path: str, json: dict[str, Any] | None = None):
    response = client.request(method, path, json=json)
    try:
        payload = response.json()
    except ValueError:
        payload = {"success": False, "error": {"message": response.text}}
    return response, payload


def _check_success(name: str, response: httpx.Response, payload: dict[str, Any]) -> bool:
    success = response.status_code < 400 and payload.get("success") is True
    detail = f"HTTP {response.status_code}"
    if not success:
        detail = f"{detail}; {payload.get('error') or payload}"
    _print_result(name, success, detail)
    return success


def _check_prediction(response: httpx.Response, payload: dict[str, Any]) -> bool:
    data = payload.get("data") or {}
    success = response.status_code < 400 and payload.get("success") is True and bool(data.get("predicted_trend"))
    detail = f"HTTP {response.status_code}"
    if success:
        detail = f"{detail}; predicted_trend={data.get('predicted_trend')}"
    else:
        detail = f"{detail}; {payload.get('error') or payload}"
    _print_result("/predict", success, detail)
    return success


def _check_market_response(name: str, response: httpx.Response, payload: dict[str, Any]) -> bool:
    data = payload.get("data") or {}
    success = (
        response.status_code < 400
        and payload.get("success") is True
        and data.get("provider") in {"binance", "coingecko", "coinpaprika"}
        and isinstance(data.get("price_usd"), (int, float))
    )
    detail = f"HTTP {response.status_code}"
    if success:
        detail = f"{detail}; provider={data.get('provider')}; price_usd={data.get('price_usd')}"
    else:
        detail = f"{detail}; {payload.get('error') or payload}"
    _print_result(name, success, detail)
    return success


def _check_analyze_defillama(name: str, response: httpx.Response, payload: dict[str, Any]) -> bool:
    data = payload.get("data") or {}
    status = data.get("defillama_status")
    success = response.status_code < 400 and payload.get("success") is True and status in {
        "available",
        "unavailable",
        "not_applicable",
        "disabled",
    }
    detail = f"HTTP {response.status_code}; defillama_status={status}"
    if not success:
        detail = f"{detail}; {payload.get('error') or payload}"
    _print_result(name, success, detail)
    return success


def _check_local_provider_order(order: str, expected: set[str]) -> bool:
    previous = os.environ.get("MARKET_PROVIDER_ORDER")
    os.environ["MARKET_PROVIDER_ORDER"] = order
    try:
        data, _ = MarketDataService().get_market_snapshot("BTC")
    except Exception as exc:
        _print_result(f"MARKET_PROVIDER_ORDER={order}", False, str(exc))
        return False
    finally:
        if previous is None:
            os.environ.pop("MARKET_PROVIDER_ORDER", None)
        else:
            os.environ["MARKET_PROVIDER_ORDER"] = previous

    provider = data.get("provider")
    ok = provider in expected
    _print_result(f"MARKET_PROVIDER_ORDER={order}", ok, f"provider={provider}; price_usd={data.get('price_usd')}")
    return ok


def _check_local_defillama_disabled() -> bool:
    previous = os.environ.get("ENABLE_DEFILLAMA_CONTEXT")
    os.environ["ENABLE_DEFILLAMA_CONTEXT"] = "false"
    try:
        data, _ = HybridAnalysisService().analyze(
            symbol="ETH",
            timeframe="1h",
            limit=120,
            question="Analyze ETH market and DeFi ecosystem risk.",
        )
    except Exception as exc:
        _print_result("ENABLE_DEFILLAMA_CONTEXT=false", False, str(exc))
        return False
    finally:
        if previous is None:
            os.environ.pop("ENABLE_DEFILLAMA_CONTEXT", None)
        else:
            os.environ["ENABLE_DEFILLAMA_CONTEXT"] = previous

    ok = data.get("defillama_status") == "disabled" and bool(data.get("answer"))
    _print_result("ENABLE_DEFILLAMA_CONTEXT=false", ok, f"defillama_status={data.get('defillama_status')}")
    return ok


def main() -> int:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()

    parser = argparse.ArgumentParser(description="Smoke test the Web3 Finance LLM backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI base URL")
    parser.add_argument("--symbol", default="BTC", help="Market symbol to test for analysis endpoints")
    parser.add_argument("--timeframe", default="1h", help="Candle timeframe")
    parser.add_argument("--limit", type=int, default=120, help="Candle limit")
    parser.add_argument("--prediction-limit", type=int, default=300, help="Candle limit for /predict")
    parser.add_argument("--horizon-days", type=int, default=3, help="Prediction horizon")
    args = parser.parse_args()

    checks: list[bool] = []
    with httpx.Client(base_url=args.base_url, timeout=180.0) as client:
        response, payload = _request(client, "GET", "/health")
        checks.append(_check_success("/health", response, payload))

        for market_symbol in ["BTC", "ETH", "SOL"]:
            response, payload = _request(client, "GET", f"/market/{market_symbol}")
            checks.append(_check_market_response(f"/market/{market_symbol}", response, payload))

        response, payload = _request(
            client,
            "POST",
            "/analyze-basic",
            {
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "limit": args.limit,
            },
        )
        checks.append(_check_success("/analyze-basic", response, payload))

        response, payload = _request(
            client,
            "POST",
            "/analyze",
            {
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "limit": args.limit,
                "question": "Why is BTC moving today and what is the short-term risk?",
            },
        )
        checks.append(_check_success("/analyze", response, payload))

        for analyze_symbol in ["ETH", "SOL", "AAVE"]:
            response, payload = _request(
                client,
                "POST",
                "/analyze",
                {
                    "symbol": analyze_symbol,
                    "timeframe": args.timeframe,
                    "limit": args.limit,
                    "question": f"Analyze {analyze_symbol} market and DeFi ecosystem risk.",
                },
            )
            checks.append(_check_analyze_defillama(f"/analyze {analyze_symbol}", response, payload))

        response, payload = _request(
            client,
            "POST",
            "/predict",
            {
                "symbol": args.symbol,
                "timeframe": "1d",
                "horizon_days": args.horizon_days,
                "limit": args.prediction_limit,
            },
        )
        checks.append(_check_prediction(response, payload))

    checks.append(_check_local_provider_order("coingecko,coinpaprika", {"coingecko", "coinpaprika"}))
    checks.append(_check_local_provider_order("coinpaprika", {"coinpaprika"}))
    checks.append(_check_local_defillama_disabled())

    if all(checks):
        print("Smoke test completed successfully.")
        return 0

    print("Smoke test failed. Check the failed endpoint message above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
