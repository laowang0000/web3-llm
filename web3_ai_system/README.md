# Web3 Finance LLM: Cryptocurrency Market Insights & Query Analyzer

Final Year Project MVP for local cryptocurrency market insight generation and query analysis.

The system combines:
- FastAPI backend endpoints for health checks, chat, market data, and analysis
- Streamlit frontend connected to the FastAPI backend
- public read-only Binance and CoinGecko market data
- technical indicators for basic market analysis
- local Ollama chat and embedding models
- local RAG with Chroma
- RAG pre-indexing script
- backend smoke test script

Do not commit `.env`, API keys, private keys, local databases, generated Chroma stores, virtual environments, caches, logs, or local model files.

## Project structure

```text
web3_ai_system/
|-- README.md
|-- requirements.txt
|-- .env.example
|-- run_streamlit.py
|-- app/
|   |-- __init__.py
|   |-- api/
|   |   |-- __init__.py
|   |   `-- main.py
|   |-- analysis/
|   |   |-- __init__.py
|   |   `-- hybrid_service.py
|   |-- config.py
|   |-- main.py
|   |-- schemas.py
|   |-- backend/
|   |   |-- __init__.py
|   |   |-- composer.py
|   |   `-- service.py
|   |-- frontend/
|   |   |-- __init__.py
|   |   `-- streamlit_app.py
|   |-- insight_engine/
|   |   |-- __init__.py
|   |   |-- embeddings.py
|   |   |-- loaders.py
|   |   |-- prompts.py
|   |   |-- rag_pipeline.py
|   |   |-- retriever.py
|   |   |-- service.py
|   |   |-- splitter.py
|   |   `-- vector_store.py
|   |-- llm/
|   |   |-- __init__.py
|   |   `-- ollama_client.py
|   |-- market_data/
|   |   |-- __init__.py
|   |   |-- binance_client.py
|   |   |-- coingecko_client.py
|   |   `-- service.py
|   |-- prediction_engine/
|   |   |-- __init__.py
|   |   |-- data_loader.py
|   |   |-- features.py
|   |   |-- model.py
|   |   |-- preprocessing.py
|   |   |-- service.py
|   |   |-- split.py
|   |   `-- trainer.py
|   |-- router/
|   |   |-- __init__.py
|   |   |-- intent_classifier.py
|   |   `-- query_router.py
|   |-- scripts/
|   |   |-- __init__.py
|   |   |-- index_rag.py
|   |   `-- smoke_test_backend.py
|   `-- utils/
|       |-- __init__.py
|       `-- logging.py
`-- data/
    `-- insight_sources/
```

## Responsibilities

- `app/config.py`: Centralized settings and constants.
- `app/schemas.py`: Shared request and response dataclasses.
- `app/main.py`: Application entrypoint used by the frontend.
- `app/backend/service.py`: Main orchestration flow.
- `app/backend/composer.py`: Formats prediction and explanation into one final output.
- `app/router/intent_classifier.py`: Rule-based query routing with optional LLM fallback.
- `app/insight_engine/`: RAG pipeline for explainable crypto insights.
- `app/prediction_engine/`: Pure numerical time-series prediction pipeline.
- `app/frontend/streamlit_app.py`: Streamlit UI that calls `/market/{symbol}`, `/analyze-basic`, and `/analyze`.
- `run_streamlit.py`: Convenience launcher for the UI.

## Recover from a fresh GitHub clone

If this computer is formatted, the project should be recoverable from GitHub plus local Ollama model downloads.

```powershell
git clone https://github.com/laowang0000/web3-llm.git
cd web3-llm/web3_ai_system
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
ollama pull qwen3.6:latest
ollama pull nomic-embed-text
python -m app.scripts.index_rag
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
python -m app.scripts.smoke_test_backend
python run_streamlit.py
```

Expected local URLs:
- FastAPI: `http://127.0.0.1:8000`
- Streamlit: `http://localhost:8501`

## Quick start

From `D:\Coding\web3 llm\web3_ai_system`:

```powershell
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
ollama serve
ollama pull qwen3.6:latest
ollama pull nomic-embed-text
```

In another terminal, pre-index RAG once before the demo:

```powershell
python -m app.scripts.index_rag
```

Start the FastAPI backend:

```powershell
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, start the Streamlit demo UI:

```powershell
python run_streamlit.py
```

You can also run Streamlit directly:

```powershell
streamlit run app/frontend/streamlit_app.py
```

After Streamlit starts, open the local URL shown in the terminal. It is usually:

```text
http://localhost:8501
```

The Streamlit UI uses `BACKEND_BASE_URL` from `.env`, defaulting to:

```text
http://127.0.0.1:8000
```

The UI supports:
- `BTCUSDT`, `ETHUSDT`, and `SOLUSDT`
- `1h`, `4h`, and `1d` timeframes
- health check from `GET /health`
- local chat from `POST /chat`
- market snapshot from `GET /market/{symbol}`
- technical indicator output from `POST /analyze-basic`
- hybrid market + RAG + Ollama explanation from `POST /analyze`

## FastAPI backend with Ollama

The MVP backend exposes frontend-ready JSON endpoints and uses a local Ollama model. No API key is required for Ollama.

1. Copy the environment template:

```powershell
copy .env.example .env
```

2. Start Ollama and pull the default model:

```powershell
ollama serve
ollama pull qwen3.6:latest
ollama pull nomic-embed-text
```

If you prefer another local chat model, update `OLLAMA_MODEL` in `.env`. If you prefer another local embedding model, update `OLLAMA_EMBED_MODEL`.

3. Start the FastAPI backend from `D:\Coding\web3 llm\web3_ai_system`:

```powershell
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

4. Test `/health`:

```powershell
curl http://127.0.0.1:8000/health
```

Expected shape:

```json
{
  "success": true,
  "data": {
    "service": "web3-finance-llm-backend",
    "status": "ok",
    "ollama": {
      "reachable": true,
      "base_url": "http://localhost:11434",
      "model": "qwen3.6:latest",
      "model_available": true,
      "available_models": ["qwen3.6:latest"]
    }
  },
  "error": null,
  "sources": []
}
```

5. Test `/chat`:

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"Explain BTC market risk in simple terms\",\"sources\":[]}"
```

Expected shape:

```json
{
  "success": true,
  "data": {
    "answer": "BTC market risk can come from volatility, liquidity, macro news, and sentiment shifts...",
    "model": "qwen3.6:latest"
  },
  "error": null,
  "sources": []
}
```

## Real market data and basic technical analysis

The backend also exposes public, read-only market data endpoints. These use Binance public spot endpoints for realtime price/OHLCV candles and CoinGecko public endpoints for market cap, volume, and 24h change. No API key is required.

Supported common symbols include `BTCUSDT`, `ETHUSDT`, and `SOLUSDT`. Short symbols such as `BTC`, `ETH`, and `SOL` are normalized to USDT pairs.

Test realtime market data:

```powershell
curl http://127.0.0.1:8000/market/BTCUSDT
```

Expected shape:

```json
{
  "success": true,
  "data": {
    "symbol": "BTCUSDT",
    "price": 65000.12,
    "binance": {
      "symbol": "BTCUSDT",
      "price": 65000.12,
      "source": "binance:/api/v3/ticker/price"
    },
    "coingecko": {
      "symbol": "BTCUSDT",
      "coin_id": "bitcoin",
      "currency": "usd",
      "price": 65010.3,
      "market_cap": 1280000000000,
      "volume_24h": 32000000000,
      "change_24h_percent": 2.4,
      "last_updated_at": 1710000000,
      "source": "coingecko:/simple/price"
    },
    "market_cap": 1280000000000,
    "volume_24h": 32000000000,
    "change_24h_percent": 2.4,
    "source_warnings": []
  },
  "error": null,
  "sources": ["binance:/api/v3/ticker/price", "coingecko:/simple/price"]
}
```

Test basic technical analysis:

```powershell
curl -X POST http://127.0.0.1:8000/analyze-basic `
  -H "Content-Type: application/json" `
  -d "{\"symbol\":\"BTCUSDT\",\"timeframe\":\"1h\",\"limit\":120}"
```

Expected shape:

```json
{
  "success": true,
  "data": {
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "price": 65000.12,
    "indicators": {
      "close": 64980.5,
      "rsi": 58.42,
      "ema_12": 64750.1,
      "ema_20": 64580.4,
      "ema_26": 64490.2,
      "ema_50": 63800.7,
      "macd": 259.9,
      "macd_signal": 210.5,
      "macd_histogram": 49.4,
      "bollinger_upper": 66010.2,
      "bollinger_middle": 64250.8,
      "bollinger_lower": 62491.4,
      "bollinger_bandwidth": 0.0548,
      "volatility_20": 0.0123
    },
    "trend": "Bullish momentum: price is above key EMAs and MACD momentum is positive.",
    "risk_flags": ["No major technical risk flag detected from the selected timeframe."],
    "latest_candle": {
      "timestamp": "2026-05-12T08:00:00+00:00",
      "open": 64800.0,
      "high": 65100.0,
      "low": 64600.0,
      "close": 64980.5,
      "volume": 1234.56
    },
    "market": {
      "market_cap": 1280000000000,
      "volume_24h": 32000000000,
      "change_24h_percent": 2.4
    }
  },
  "error": null,
  "sources": ["binance:/api/v3/ticker/price", "coingecko:/simple/price", "binance:/api/v3/klines"]
}
```

Test hybrid market + RAG + Ollama analysis:

```powershell
curl -X POST http://127.0.0.1:8000/analyze `
  -H "Content-Type: application/json" `
  -d "{\"symbol\":\"BTCUSDT\",\"timeframe\":\"1h\",\"limit\":120,\"question\":\"Why is BTC moving today and what is the short-term risk?\"}"
```

Expected shape:

```json
{
  "success": true,
  "data": {
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "price": 65000.12,
    "indicators": {
      "rsi": 58.42,
      "ema_20": 64580.4,
      "macd": 259.9,
      "bollinger_upper": 66010.2,
      "volatility_20": 0.0123
    },
    "trend": "Bullish momentum: price is above key EMAs and MACD momentum is positive.",
    "risk_flags": ["No major technical risk flag detected from the selected timeframe."],
    "answer": "Based on the provided market data, BTC shows positive short-term momentum, while retrieved context is limited...",
    "model": "qwen3.6:latest",
    "retrieved_context_count": 3,
    "retrieved_sources": [
      {
        "source_name": "monthly-market-insights-2026-02.pdf",
        "source_type": "rag_raw",
        "source_path": "D:\\Coding\\web3 llm\\rag\\raw\\monthly-market-insights-2026-02.pdf",
        "page": 1,
        "preview": "..."
      }
    ]
  },
  "error": null,
  "sources": ["binance:/api/v3/ticker/price", "coingecko:/simple/price", "binance:/api/v3/klines", "rag_raw::monthly-market-insights-2026-02.pdf#page=1"]
}
```

## Demo verification scripts

### Pre-index RAG before demo

Run this once before a demo so `/analyze` does not spend the first request parsing PDFs and creating embeddings.

Requirements:
- Ollama must be running.
- The local embedding model must be available.

```powershell
ollama serve
ollama pull nomic-embed-text
python -m app.scripts.index_rag
```

Expected pass output:

```text
RAG pre-indexing
================
Embedding provider: ollama
Embedding model: nomic-embed-text
Ollama base URL: http://localhost:11434
Document pages/files loaded: 120
Chunks generated: 850
Chunks indexed in Chroma: 850
Chroma path: D:\Coding\web3 llm\web3_ai_system\storage\chroma_insight
Indexed sources:
- crypto_news::btc_etf_flow.txt: 1 document item(s)
- rag_raw::monthly-market-insights-2026-02.pdf: 30 document item(s)
RAG pre-indexing completed successfully.
```

Expected fail output if Ollama or the embedding model is unavailable:

```text
ERROR: Ollama embedding model is unavailable: ...
Fix: run `ollama serve` and `ollama pull nomic-embed-text`.
```

### Smoke test backend

Start FastAPI first:

```powershell
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Then run:

```powershell
python -m app.scripts.smoke_test_backend
```

Expected pass output:

```text
[PASS] /health: HTTP 200
[PASS] /market/BTCUSDT: HTTP 200
[PASS] /analyze-basic: HTTP 200
[PASS] /analyze: HTTP 200
Smoke test completed successfully.
```

Expected fail output:

```text
[FAIL] /analyze: HTTP 502; {'code': 'HYBRID_ANALYSIS_FAILED', 'message': '...'}
Smoke test failed. Check the failed endpoint message above.
```

## Insight engine

The RAG insight engine uses:
- LangChain
- local Ollama embeddings via `nomic-embed-text`
- Chroma vector store
- source-aware metadata for explainability

Only a small demo RAG dataset is committed to GitHub. Large PDF collections, private reports, paid research, personal documents, generated Chroma indexes, and local vector databases are excluded from Git. Keep extra local PDFs in `rag/raw/` only on your machine unless they are intentionally reviewed and allowlisted in `.gitignore`.

Data is expected under:

```text
data/insight_sources/
|-- crypto_news/
|-- on_chain_summaries/
`-- market_reports/

rag/raw/
`-- optional sample PDF reports
```

Each source can contain `.txt`, `.md`, or `.pdf` files. The engine:
- loads documents from those folders
- chunks them with overlap
- embeds chunks with local Ollama embeddings by default
- stores them in Chroma
- retrieves top-k chunks
- passes retrieved context into Ollama for grounded answers

OpenAI embeddings are only an optional fallback. To use them explicitly, set `EMBEDDING_PROVIDER=openai` and configure your OpenAI environment separately.

## Prediction engine

The prediction engine uses:
- XGBoost classification
- structured numerical inputs only
- chronological train/test splitting
- forward-shifted labels for `UP` and `DOWN` trend prediction

Core features include:
- `price`
- `volume`
- `RSI`
- `EMA`
- `MACD`

Leakage is reduced by:
- sorting data by timestamp before processing
- computing indicators from current and past rows only
- creating the target from future price movement after features are built
- using a time-series split instead of random shuffling
