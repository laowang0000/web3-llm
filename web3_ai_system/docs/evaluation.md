# Evaluation Checklist

This checklist supports the FYP demo evidence collection for the dual-engine MVP.

| Test Item | Endpoint/UI | Expected Result | Evidence to Capture | Status |
|---|---|---|---|---|
| Health check | `/health` | HTTP 200 | terminal/API screenshot | PASS after test |
| Market data | `/market/BTCUSDT` | price data returned | API screenshot | PASS after test |
| Technical analysis | `/analyze-basic` | RSI/EMA/MACD returned | Streamlit/API screenshot | PASS after test |
| Live news | `/news/BTCUSDT` | Marketaux/GNews article snippets or clear warnings | API/Streamlit screenshot | PASS after test |
| RAG insight | `/analyze` | LLM answer + retrieved sources | Streamlit screenshot | PASS after test |
| Prediction | `/predict` | trend + probability returned | Streamlit/API screenshot | PASS after test |
| Visualisation | Streamlit | close price and RSI/MACD chart shown | UI screenshot | PASS after test |

## Notes for Report

- Describe `/predict` metrics as demo backtest metrics only.
- Do not describe the system as a financial adviser or trading bot.
- Do not claim real wallet tracking, live on-chain transaction analysis, or persistent live social media/news ingestion.
- If using Marketaux/GNews in the demo, describe it as on-demand live article augmentation for `/news` and `/analyze`, not as a stored news data warehouse.
- Treat RAG answers as local-document-grounded explanations whose quality depends on indexed sources.
