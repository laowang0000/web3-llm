import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


DEFAULT_DEFILLAMA_BASE_URL = "https://api.llama.fi"
DEFAULT_TIMEOUT_SECONDS = 10.0
INTERPRETATION_HINTS = [
    "Falling TVL may indicate weaker DeFi liquidity.",
    "Rising TVL may indicate stronger ecosystem capital inflow.",
    "DeFiLlama context reflects ecosystem fundamentals, not direct price prediction.",
]
SYMBOL_TO_CHAIN = {
    "ETH": "Ethereum",
    "SOL": "Solana",
    "MATIC": "Polygon",
    "POL": "Polygon",
    "BNB": "BSC",
    "AVAX": "Avalanche",
    "ARB": "Arbitrum",
    "OP": "Optimism",
    "BASE": "Base",
}
EXCLUDED_PROTOCOL_CATEGORIES = {"cex"}
SYMBOL_TO_PROTOCOL = {
    "AAVE": "aave",
    "UNI": "uniswap",
    "LDO": "lido",
    "CRV": "curve-finance",
    "MKR": "makerdao",
    "PENDLE": "pendle",
    "JUP": "jupiter",
    "RAY": "raydium",
}


class DefiLlamaClientError(RuntimeError):
    """Raised when DeFiLlama data cannot be fetched or normalized."""


@dataclass(frozen=True)
class DefiLlamaSettings:
    base_url: str
    timeout_seconds: float


def _load_environment() -> None:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()


def get_defillama_settings() -> DefiLlamaSettings:
    _load_environment()
    return DefiLlamaSettings(
        base_url=os.getenv("DEFILLAMA_BASE_URL", DEFAULT_DEFILLAMA_BASE_URL).rstrip("/"),
        timeout_seconds=float(os.getenv("DEFILLAMA_REQUEST_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))),
    )


def defillama_context_enabled() -> bool:
    _load_environment()
    return os.getenv("ENABLE_DEFILLAMA_CONTEXT", "true").strip().lower() in {"1", "true", "yes", "on"}


class DefiLlamaClient:
    """Read-only client for compact DeFiLlama ecosystem context."""

    def __init__(self, settings: DefiLlamaSettings | None = None) -> None:
        self.settings = settings or get_defillama_settings()

    def _get(self, path: str) -> Any:
        url = f"{self.settings.base_url}{path}"
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise DefiLlamaClientError("DeFiLlama request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise DefiLlamaClientError(
                f"DeFiLlama returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"
            ) from exc
        except httpx.RequestError as exc:
            raise DefiLlamaClientError(f"Could not connect to DeFiLlama: {exc}") from exc
        except ValueError as exc:
            raise DefiLlamaClientError("DeFiLlama returned invalid JSON.") from exc

    def get_chains(self) -> list[dict[str, Any]]:
        payload = self._get("/v2/chains")
        if not isinstance(payload, list):
            raise DefiLlamaClientError("Unexpected DeFiLlama chains response format.")
        return payload

    def get_protocols(self) -> list[dict[str, Any]]:
        payload = self._get("/protocols")
        if not isinstance(payload, list):
            raise DefiLlamaClientError("Unexpected DeFiLlama protocols response format.")
        return payload

    def get_protocol(self, slug: str) -> dict[str, Any]:
        normalized_slug = slug.strip().lower()
        if not normalized_slug:
            raise DefiLlamaClientError("Protocol slug is required.")
        payload = self._get(f"/protocol/{normalized_slug}")
        if not isinstance(payload, dict):
            raise DefiLlamaClientError("Unexpected DeFiLlama protocol response format.")
        payload.setdefault("slug", normalized_slug)
        return self._normalize_protocol_detail(payload)

    def get_chain_context(self, chain_name: str) -> dict[str, Any]:
        chain = self._find_chain(chain_name)
        return {
            "chain": chain.get("name") or chain_name,
            "tvl": _optional_float(chain.get("tvl")),
            "change_1d": _optional_float(chain.get("change_1d")),
            "change_7d": _optional_float(chain.get("change_7d")),
            "change_1m": _optional_float(chain.get("change_1m")),
            "source": "defillama",
        }

    def get_top_protocols_by_chain(self, chain_name: str, limit: int = 5) -> list[dict[str, Any]]:
        protocols = self.get_protocols()
        target = _normalize_name(chain_name)
        matches = [
            protocol
            for protocol in protocols
            if any(_normalize_name(chain) == target for chain in protocol.get("chains") or [])
            and _normalize_name(protocol.get("category")) not in EXCLUDED_PROTOCOL_CATEGORIES
        ]
        matches.sort(key=lambda protocol: _latest_protocol_tvl(protocol) or 0.0, reverse=True)
        return [self._normalize_protocol_summary(protocol) for protocol in matches[: max(1, limit)]]

    def build_symbol_context(self, symbol: str) -> dict[str, Any] | None:
        base_symbol = _base_symbol(symbol)
        chain_name = SYMBOL_TO_CHAIN.get(base_symbol)
        protocol_slug = SYMBOL_TO_PROTOCOL.get(base_symbol)
        if not chain_name and not protocol_slug:
            return None

        chain_context = self.get_chain_context(chain_name) if chain_name else None
        top_protocols = self.get_top_protocols_by_chain(chain_name, limit=5) if chain_name else []
        protocol_context = self.get_protocol(protocol_slug) if protocol_slug else None

        return {
            "source": "defillama",
            "chain_context": chain_context,
            "protocol_context": protocol_context,
            "top_protocols": top_protocols,
            "interpretation_hints": INTERPRETATION_HINTS,
        }

    def _find_chain(self, chain_name: str) -> dict[str, Any]:
        target = _normalize_name(chain_name)
        for chain in self.get_chains():
            if _normalize_name(chain.get("name")) == target:
                return chain
        raise DefiLlamaClientError(f"No DeFiLlama chain context found for {chain_name}.")

    def _normalize_protocol_summary(self, protocol: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": protocol.get("name"),
            "slug": protocol.get("slug"),
            "category": protocol.get("category"),
            "tvl": _latest_protocol_tvl(protocol),
            "change_7d": _optional_float(protocol.get("change_7d")),
        }

    def _normalize_protocol_detail(self, protocol: dict[str, Any]) -> dict[str, Any]:
        current_chain_tvls = protocol.get("currentChainTvls") or {}
        chain_distribution = [
            {"chain": chain, "tvl": _optional_float(tvl)}
            for chain, tvl in current_chain_tvls.items()
            if isinstance(tvl, (int, float)) and not str(chain).lower().endswith("-borrowed")
        ]
        chain_distribution.sort(key=lambda row: row.get("tvl") or 0.0, reverse=True)
        return {
            "name": protocol.get("name"),
            "slug": protocol.get("slug"),
            "category": protocol.get("category"),
            "tvl": _latest_protocol_tvl(protocol),
            "change_1d": _optional_float(protocol.get("change_1d")),
            "change_7d": _optional_float(protocol.get("change_7d")),
            "change_1m": _optional_float(protocol.get("change_1m")),
            "chains": protocol.get("chains") or [],
            "chain_distribution": chain_distribution[:8],
            "source": "defillama",
        }


def _base_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("-", "").replace("/", "")
    return normalized[:-4] if normalized.endswith("USDT") else normalized


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_protocol_tvl(protocol: dict[str, Any]) -> float | None:
    tvl = protocol.get("tvl")
    numeric_tvl = _optional_float(tvl)
    if numeric_tvl is not None:
        return numeric_tvl
    if isinstance(tvl, list) and tvl:
        latest = tvl[-1]
        if isinstance(latest, dict):
            return _optional_float(latest.get("totalLiquidityUSD"))
    current_chain_tvls = protocol.get("currentChainTvls") or {}
    if isinstance(current_chain_tvls, dict):
        values = [
            _optional_float(value)
            for chain, value in current_chain_tvls.items()
            if not str(chain).lower().endswith("-borrowed")
        ]
        numeric_values = [value for value in values if value is not None]
        if numeric_values:
            return sum(numeric_values)
    return None
