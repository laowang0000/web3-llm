# Web3 LLM Project Memory Migration Report

Generated on 2026-06-08 from current workspace inspection plus Codex memory notes.

## 1. Project Identity

Primary project:

- Workspace root: `D:\Coding\web3 llm`
- Backend/FYP project: `D:\Coding\web3 llm\web3_ai_system`
- Final React UI: `D:\Coding\web3 llm\crypto-ai-dashboard`
- Related local RAG source folder: `D:\Coding\web3 llm\rag\raw`

This is a Final Year Project MVP named **Web3 Finance LLM: Cryptocurrency Market Insights & Query Analyzer**. The project is an academic demo for cryptocurrency market insight generation, hybrid LLM/RAG analysis, and short-term numerical trend prediction.

The most important framing to preserve is that this is a **dual-engine system**:

1. **Insight Engine**: local Ollama LLM + local RAG + Chroma + optional news/DeFi context. This powers explanation-oriented analysis through `/analyze`.
2. **Prediction Engine**: numerical OHLCV candles + technical indicators + classifier pipeline. This powers short-term trend classification through `/predict`.

Do not describe prediction as LLM-based. Do not describe the LLM/RAG analysis and the numerical prediction path as the same model.

## 2. User Preferences And Working Style

The user prefers:

- Small, stable, demo-ready edits.
- Existing project structure preserved as much as possible.
- Backward-compatible endpoint contracts.
- Clear separation between implemented code and report-only claims.
- Code-grounded explanations that map feature -> API endpoint -> implementation file -> external dependency.
- Honest limitations instead of polished but unsupported claims.
- No fake OHLCV candles, no synthetic prediction accuracy, and no overstated model performance.
- Secrets and provider config in `.env` / `.env.example`, not hardcoded in Python.
- Streamlit treated as a backend functional testing console only.
- React treated as the final presentation UI.
- Backend service-layer changes over frontend-only patches for core behavior.

When answering project questions, prefer operational language and concrete paths over generic product descriptions.

## 3. Current Technical Stack

Backend:

- Python
- FastAPI
- Uvicorn
- httpx async clients
- python-dotenv
- pandas / numpy
- scikit-learn
- XGBoost
- LangChain
- ChromaDB
- pypdf
- local Ollama chat and embedding models

Frontend/testing:

- Streamlit functional testing console in `web3_ai_system/app/frontend/streamlit_app.py`
- React 18 + Vite final UI in `crypto-ai-dashboard`
- Tailwind CSS for final UI styling

Local AI/runtime:

- Default chat model: `qwen3.5:9b`
- Default embedding model: `nomic-embed-text`
- Ollama base URL: `http://localhost:11434`
- Chroma local vector store

Market/news/data providers:

- Binance public read-only endpoints
- CoinGecko public endpoints
- CoinPaprika fallback endpoints
- Optional DeFiLlama context
- Optional Marketaux and GNews live news snippets

## 4. Main API Surface

Current quick scan of `web3_ai_system/app/api/main.py` found these routes:

- `GET /`
- `GET /health`
- `GET /runtime/status`
- `GET /models/ollama`
- `POST /models/test-connection`
- `POST /chat`
- `GET /market/{symbol}`
- `POST /analyze-basic`
- `GET /news/{symbol}`
- `POST /analyze`
- `POST /predict`

Older memories said root `/` returned `404`; the current file now contains a `GET /` route, so treat that older troubleshooting note as stale unless verified against the running app.

Important endpoint responsibilities:

- `/health`: backend status and Ollama availability check.
- `/chat`: direct local chat through configured model.
- `/market/{symbol}`: market snapshot.
- `/analyze-basic`: technical-indicator-only analysis.
- `/news/{symbol}`: optional live news snippets if keys are configured.
- `/analyze`: hybrid path combining market/technical context, RAG, optional news, optional DeFiLlama, and Ollama.
- `/predict`: numerical trend prediction using OHLCV + technical features, not LLM.

## 5. Architecture Map

Key files:

- `web3_ai_system/app/api/main.py`: FastAPI routes and endpoint response envelopes.
- `web3_ai_system/app/config.py`: central settings and environment config.
- `web3_ai_system/app/schemas.py`: request/response dataclasses.
- `web3_ai_system/app/backend/service.py`: main orchestration flow.
- `web3_ai_system/app/backend/composer.py`: final output formatting.
- `web3_ai_system/app/analysis/hybrid_service.py`: hybrid analysis flow.
- `web3_ai_system/app/market_data/service.py`: market-data coordination and provider fallback.
- `web3_ai_system/app/market_data/binance_client.py`: Binance public market client.
- `web3_ai_system/app/market_data/coingecko_client.py`: CoinGecko client.
- `web3_ai_system/app/market_data/coinpaprika_client.py`: CoinPaprika client.
- `web3_ai_system/app/news_data/service.py`: Marketaux/GNews live-news orchestration.
- `web3_ai_system/app/defi_data/defillama_client.py`: optional DeFiLlama context.
- `web3_ai_system/app/insight_engine/`: RAG loading, splitting, embedding, vector store, retrieval, prompts.
- `web3_ai_system/app/llm/ollama_client.py`: Ollama chat client.
- `web3_ai_system/app/prediction_engine/`: OHLCV preprocessing, feature engineering, model training, prediction service.
- `web3_ai_system/app/frontend/streamlit_app.py`: Streamlit backend verification console.
- `crypto-ai-dashboard/src/App.jsx`: final React UI consuming FastAPI JSON responses.

## 6. Historical Decisions To Preserve

### Dual-system framing

The user repeatedly clarified that LLM/RAG and prediction are separate deliverables with separate evidence needs.

- LLM/RAG path: explanation, retrieval, market/news/DeFi context, Ollama generation.
- Prediction path: OHLCV candles, technical indicators, chronological split, XGBoost/sklearn classifier fallback.

### Frontend boundary

Streamlit is not the final UI. It is a functional testing console.

React is the final presentation/testing UI and should call backend JSON endpoints directly. Do not duplicate prediction, RAG, market-data, or LLM logic in React.

### Provider fallback belongs in backend services

Market provider ordering, normalization, timeout handling, and graceful degradation should live in `MarketDataService`, not in UI code.

The remembered provider-order contract is:

```env
MARKET_PROVIDER_ORDER=binance,coingecko,coinpaprika
MARKET_REQUEST_TIMEOUT=10
```

Future fallback work should preserve Binance where possible, then fall back through CoinGecko and CoinPaprika where the data shape supports the endpoint.

### Prediction honesty

Prediction requires historical OHLCV data with fields like:

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`

If a fallback provider only returns latest ticker/snapshot data, do not invent candles. Return a transparent limitation instead.

### News/RAG scope

RAG does not inherently require a live News API. It needs retrievable source material, which can be PDFs, local text files, cached news, RSS, or scraped sources.

For this FYP, the most demo-stable pattern is:

1. Periodic news ingestion.
2. Save locally under a controlled data folder.
3. Index into the existing RAG pipeline.
4. Show retrieved sources in `/analyze`.

Marketaux was previously recommended as the best fit because it is finance-oriented and demo-friendly. GNews was the second choice. Live news keys are optional.

### Report alignment

The main historical gap was not the lack of a baseline demo API. It was wording mismatch between the FYP report and the implemented prototype, especially around:

- full live on-chain analytics,
- wallet tracking,
- Dune / Arkham / CryptoQuant / Etherscan / Alchemy,
- persistent social/news ingestion.

README now explicitly says these are not implemented. Keep that honesty in future report/demo work.

## 7. Runtime And Demo Commands

From:

```powershell
cd "D:\Coding\web3 llm\web3_ai_system"
```

Full Streamlit functional test demo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start_demo.ps1
```

Double-click wrapper:

```text
start_demo.bat
```

Final React presentation UI:

```powershell
.\start_final_ui.bat
```

Stop FastAPI and Streamlit:

```powershell
.\scripts\stop_demo.ps1
```

Backend-only fallback if port 8000 is busy or only FastAPI is needed:

```powershell
.\scripts\start_backend.ps1 -Port 8001
```

Expected local URLs:

- FastAPI: `http://127.0.0.1:8000`
- FastAPI docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`
- React final UI: `http://127.0.0.1:5173`
- Streamlit console: `http://localhost:8501`

## 8. Verification Habits

Preferred regression order for news/RAG or backend changes:

1. Baseline endpoints: `/health`, `/market/BTCUSDT`, `/analyze-basic`, `/analyze`, `/predict`.
2. News API only.
3. Save/cache news locally.
4. RAG indexing.
5. `/analyze` retrieved-source visibility.
6. Confirm `/predict` remains independent from news/RAG.
7. Streamlit flow.
8. Failure cases.
9. Full demo launcher.

Useful checks:

```powershell
python -m app.scripts.index_rag
python -m app.scripts.smoke_test_backend
```

PowerShell script syntax check remains useful when full execution is not possible:

```powershell
[System.Management.Automation.Language.Parser]::ParseFile("scripts\start_demo.ps1", [ref]$null, [ref]$null)
```

If Python is missing on PATH in Codex, previous runs used:

```text
C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

## 9. Environment And Secrets

Do not commit:

- `.env`
- API keys
- private keys
- local Chroma stores
- virtual environments
- caches
- logs
- local model files

Important `.env.example` settings currently include:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_EMBED_MODEL=nomic-embed-text
EMBEDDING_PROVIDER=ollama
RAG_TOP_K=3
API_HOST=127.0.0.1
API_PORT=8000
BACKEND_BASE_URL=http://127.0.0.1:8000
BINANCE_BASE_URL=https://api.binance.com
COINGECKO_BASE_URL=https://api.coingecko.com/api/v3
COINPAPRIKA_BASE_URL=https://api.coinpaprika.com/v1
MARKET_PROVIDER_ORDER=binance,coingecko,coinpaprika
MARKET_REQUEST_TIMEOUT=10
ENABLE_DEFILLAMA_CONTEXT=true
MARKETAUX_API_TOKEN=
GNEWS_API_KEY=
NEWS_MAX_ARTICLES=3
```

## 10. Current Workspace Caution

At report generation time, the Git working tree under `D:\Coding\web3 llm` was dirty. Many core backend/frontend files were modified, and some files were untracked, including:

- `crypto-ai-dashboard/.env.example`
- `web3_ai_system/app/defi_data/`
- `web3_ai_system/app/market_data/coinpaprika_client.py`
- `web3_ai_system/app/scripts/check_rag_index.py`
- `web3_ai_system/app/scripts/test_defillama_client.py`
- `web3_ai_system/app/scripts/test_market_providers.py`
- `web3_ai_system/prepare_rag_index.bat`

Before a new account makes edits, it should inspect `git status --short` and avoid reverting user changes.

## 11. Migration Prompt For Another Account

Use this as the initial memory seed in the other account:

```text
I am working on a Windows Codex workspace project at D:\Coding\web3 llm. The main FYP repo is web3_ai_system and the final UI is crypto-ai-dashboard.

Preserve the dual-engine architecture:
- /analyze is LLM/RAG-based, using local Ollama qwen3.5:9b, nomic-embed-text embeddings, Chroma, local documents, optional Marketaux/GNews news, and optional DeFiLlama context.
- /predict is not LLM-based. It uses historical OHLCV, technical indicators, chronological train/test split, and XGBoost/sklearn classifier fallback.

Default to small, stable, demo-ready edits. Keep endpoint contracts working. Keep Streamlit as backend functional testing only and React as the final presentation UI. Do not move core logic into React. Do not fake OHLCV, synthetic candles, or inflated prediction accuracy. Keep secrets in .env/.env.example.

Key endpoints include /health, /chat, /market/{symbol}, /analyze-basic, /news/{symbol}, /analyze, and /predict. Current code also appears to include /, /runtime/status, /models/ollama, and /models/test-connection.

Market provider fallback should live in MarketDataService with configured order binance,coingecko,coinpaprika. Missing news API keys should warn/degrade gracefully, not break the demo. RAG does not require a live News API; local/cached sources are acceptable.

For local demo startup use web3_ai_system/scripts/start_demo.ps1 for Streamlit functional testing, start_final_ui.bat for the final React UI, stop_demo.ps1 for port cleanup, and start_backend.ps1 -Port 8001 for backend-only fallback. Check /health and /docs, not just root.

The project report must separate implemented functionality from report-only claims. No wallet tracking, private key handling, transaction execution, full on-chain analytics, Dune/Arkham/CryptoQuant/Etherscan/Alchemy integration, or persistent social/news ingestion should be claimed unless implemented later.
```

