# Web3 Finance LLM Final UI

Polished React + Tailwind presentation layer for the FYP demo.

This UI does not contain prediction, RAG, market-data, or LLM logic. It only calls the FastAPI backend and renders JSON responses from:

- `GET /health`
- `POST /analyze`
- `POST /predict`

Use Streamlit as the functional testing and fallback UI. Use this React UI for final demo screenshots and presentation.

## Run With Backend

From the repository root:

```powershell
cd web3_ai_system
.\start_final_ui.bat
```

Then open:

```text
http://127.0.0.1:5173
```

## Frontend Only

Only use this after FastAPI is already running at `http://127.0.0.1:8000`.

```powershell
cd crypto-ai-dashboard
npm install
npm run dev -- --host 127.0.0.1
```

## Structure

```text
crypto-ai-dashboard/
|-- index.html
|-- package.json
|-- vite.config.js
|-- tailwind.config.js
`-- src/
    |-- App.jsx
    |-- main.jsx
    |-- styles.css
    |-- components/
    |   |-- Header.jsx
    |   |-- Sidebar.jsx
    |   `-- icons.jsx
    `-- data/
        `-- marketData.js
```
