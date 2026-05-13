import argparse
from typing import Any

import httpx


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the Web3 Finance LLM backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI base URL")
    parser.add_argument("--symbol", default="BTCUSDT", help="Market symbol to test")
    parser.add_argument("--timeframe", default="1h", help="Candle timeframe")
    parser.add_argument("--limit", type=int, default=120, help="Candle limit")
    args = parser.parse_args()

    checks: list[bool] = []
    with httpx.Client(base_url=args.base_url, timeout=180.0) as client:
        response, payload = _request(client, "GET", "/health")
        checks.append(_check_success("/health", response, payload))

        response, payload = _request(client, "GET", f"/market/{args.symbol}")
        checks.append(_check_success(f"/market/{args.symbol}", response, payload))

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

    if all(checks):
        print("Smoke test completed successfully.")
        return 0

    print("Smoke test failed. Check the failed endpoint message above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

