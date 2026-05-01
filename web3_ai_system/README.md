# Web3 AI System

A modular starter project for a hybrid Web3 AI application with:
- RAG Insight Engine
- Prediction Engine
- Query Router
- Streamlit frontend

## Project structure

```text
web3_ai_system/
|-- README.md
|-- requirements.txt
|-- run_streamlit.py
|-- app/
|   |-- __init__.py
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
- `app/frontend/streamlit_app.py`: Streamlit UI.
- `run_streamlit.py`: Convenience launcher for the UI.

## Quick start

From `D:\Coding\web3 llm\web3_ai_system`:

```bash
pip install -r requirements.txt
set OPENAI_API_KEY=your_key_here
python run_streamlit.py
```

You can also run:

```bash
streamlit run app/frontend/streamlit_app.py
```

After Streamlit starts, open the local URL shown in the terminal. It is usually:

```text
http://localhost:8501
```

## Insight engine

The RAG insight engine uses:
- LangChain
- OpenAI embeddings via `text-embedding-3-small`
- Chroma vector store
- source-aware metadata for explainability

Data is expected under:

```text
data/insight_sources/
|-- crypto_news/
|-- on_chain_summaries/
`-- market_reports/
```

Each source can contain `.txt` or `.md` files. The engine:
- loads documents from those folders
- chunks them with overlap
- embeds chunks with OpenAI embeddings
- stores them in Chroma
- retrieves top-k chunks
- generates grounded answers with cited sources

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
