from pathlib import Path

from dotenv import load_dotenv

from app.defi_data.defillama_client import DefiLlamaClient


def _print_result(name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def main() -> int:
    project_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(project_env)
    load_dotenv()

    client = DefiLlamaClient()
    checks: list[bool] = []

    try:
        chains = client.get_chains()
        ok = bool(chains)
        _print_result("GET /v2/chains", ok, f"chains_count={len(chains)}")
        checks.append(ok)
    except Exception as exc:
        _print_result("GET /v2/chains", False, str(exc))
        checks.append(False)

    for chain_name in ["Ethereum", "Solana"]:
        try:
            chain_context = client.get_chain_context(chain_name)
            ok = chain_context.get("chain") == chain_name and isinstance(chain_context.get("tvl"), (int, float))
            _print_result(
                f"Filter {chain_name}",
                ok,
                f"tvl={chain_context.get('tvl')}; change_7d={chain_context.get('change_7d')}",
            )
            checks.append(ok)
        except Exception as exc:
            _print_result(f"Filter {chain_name}", False, str(exc))
            checks.append(False)

    try:
        protocol = client.get_protocol("aave")
        ok = protocol.get("slug") == "aave" and isinstance(protocol.get("tvl"), (int, float))
        _print_result("GET /protocol/aave", ok, f"name={protocol.get('name')}; tvl={protocol.get('tvl')}")
        checks.append(ok)
    except Exception as exc:
        _print_result("GET /protocol/aave", False, str(exc))
        checks.append(False)

    try:
        top_protocols = client.get_top_protocols_by_chain("Ethereum", limit=5)
        ok = 1 <= len(top_protocols) <= 5 and all("name" in protocol for protocol in top_protocols)
        names = ", ".join(str(protocol.get("name")) for protocol in top_protocols)
        _print_result("Top 5 Ethereum protocols", ok, f"count={len(top_protocols)}; names={names}")
        checks.append(ok)
    except Exception as exc:
        _print_result("Top 5 Ethereum protocols", False, str(exc))
        checks.append(False)

    if all(checks):
        print("DeFiLlama client test completed successfully.")
        return 0
    print("DeFiLlama client test failed. Check the compact error above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
