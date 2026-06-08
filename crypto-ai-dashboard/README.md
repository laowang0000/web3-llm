# Web3 Finance LLM Final UI

Polished React + Tailwind presentation/testing layer for the FYP final UI.

React is the final testing/demo UI. It calls FastAPI through `VITE_API_BASE_URL` and only displays data returned from FastAPI JSON endpoints.

Use this default local backend target:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

This UI does not contain prediction, RAG, market-data, news, DeFiLlama, or LLM logic. It only calls the FastAPI backend and renders JSON responses from:

- `GET /health`
- `GET /models/ollama`
- `POST /models/test-connection`
- `POST /analyze`
- `POST /predict`

Use Streamlit as the functional testing console. Use this React UI for final screenshots and presentation.

The React UI does not expose separate mode toggles for context loading. It renders the backend runtime status panel for Smart Context Selection, including selected model, response mode, prompt context type, included contexts, and fallback status.

The Model Settings page controls chat/generation providers only: Local Ollama, Remote Ollama, or an OpenAI-compatible API endpoint. The embedding model remains fixed at `nomic-embed-text` for RAG index consistency, and API keys are kept in React state only unless the user explicitly changes the code to persist them.

## Frontend Responsibility

React handles user interaction and visual presentation. FastAPI handles market data, RAG, news, DeFiLlama, prediction, technical indicators, and LLM orchestration.

Streamlit is only a functional testing console for backend verification. New final UI behavior should be implemented in React and backed by FastAPI JSON endpoints, not added only to Streamlit.

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

Optional local override:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
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
