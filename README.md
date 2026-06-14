# Web3 LLM Crypto Risk Analysis System

Final Year Project repository for a local Web3 finance assistant that combines LLM-based market explanation with numerical short-term crypto trend prediction.

The project is built as a dual-engine academic MVP:

- Insight Engine: FastAPI, local Ollama, Chroma RAG, optional live news, optional DeFiLlama context, and source-aware market-risk explanation through `/analyze`.
- Prediction Engine: Binance OHLCV candles, technical indicators, and an XGBoost trend classifier through `/predict`.
- Final UI: React + Tailwind dashboard that calls the backend API and displays analysis, prediction, runtime status, and model settings.
- Functional test UI: Streamlit console for backend verification during demos.

This is an academic prototype, not a trading bot or financial adviser. It does not execute trades, manage wallets, handle private keys, or provide guaranteed predictions.

## Repository Layout

```text
.
|-- web3_ai_system/          # FastAPI backend, RAG, prediction engine, Streamlit test console
|-- crypto-ai-dashboard/     # React + Tailwind final presentation UI
|-- rag/raw/                 # Allowlisted demo PDF sources for local RAG indexing
|-- hybrid_ai_system_design.md
`-- README.md
```

## Main Capabilities

- Health and runtime checks: `GET /health`
- Ollama model listing and connection testing: `GET /models/ollama`, `POST /models/test-connection`
- Read-only market data: `GET /market/{symbol}`
- Technical indicator analysis: `POST /analyze-basic`
- RAG + market + news + DeFiLlama market-risk analysis: `POST /analyze`
- Short-term trend classification: `POST /predict`

Common demo symbols include `BTCUSDT`, `ETHUSDT`, and `SOLUSDT`.

## Quick Start

From a fresh clone on Windows PowerShell:

```powershell
git clone https://github.com/laowang0000/web3-llm.git
cd web3-llm\web3_ai_system
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
ollama pull qwen3.5:9b
ollama pull nomic-embed-text
python -m app.scripts.index_rag
```

Start the final React UI and FastAPI backend together:

```powershell
.\start_final_ui.bat
```

Expected local URLs:

- React final UI: `http://127.0.0.1:5173`
- FastAPI backend: `http://127.0.0.1:8000`
- FastAPI docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## Manual Development Commands

Backend:

```powershell
cd web3_ai_system
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd crypto-ai-dashboard
npm ci
npm run dev -- --host 127.0.0.1
```

Streamlit functional testing console:

```powershell
cd web3_ai_system
python run_streamlit.py
```

## Environment

Backend configuration starts from:

```text
web3_ai_system/.env.example
```

Frontend configuration starts from:

```text
crypto-ai-dashboard/.env.example
```

Default local runtime:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_EMBED_MODEL=nomic-embed-text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Optional live news keys can be added locally for Marketaux and GNews. Do not commit `.env`, API keys, Chroma stores, virtual environments, caches, logs, or generated local data.

## Verification

Backend smoke test, after FastAPI is running:

```powershell
cd web3_ai_system
python -m app.scripts.smoke_test_backend
```

Frontend production build:

```powershell
cd crypto-ai-dashboard
npm run build
```

Useful test endpoints:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/market/BTCUSDT
curl -X POST http://127.0.0.1:8000/analyze-basic -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSDT\",\"timeframe\":\"1h\",\"limit\":120}"
curl -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSDT\",\"timeframe\":\"1d\",\"horizon_days\":3,\"limit\":300}"
```

## Project Boundaries

The prototype intentionally keeps the LLM/RAG analysis path separate from the numerical prediction path:

- `/analyze` is for market-risk explanation using selected context.
- `/predict` is for OHLCV-based short-term trend classification.

Prediction metrics are demo backtest metrics from the requested candle window. They should not be described as production trading performance or as a guaranteed accuracy claim.

For more detail, see:

- `web3_ai_system/README.md`
- `crypto-ai-dashboard/README.md`
- `web3_ai_system/docs/evaluation.md`
