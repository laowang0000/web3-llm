# LLM-based Cryptocurrency Market Insights & Query Analyzer

## 1. Extracted Key Content from the FYP Report

### 1.1 Project theme
The report proposes a Web3 finance analytics system that helps users query blockchain and cryptocurrency information using natural language. The original prototype centers on an LLM-driven interface supported by Retrieval-Augmented Generation (RAG) to interpret on-chain data, off-chain market information, and unstructured text such as news and social media.

### 1.2 Problem addressed
The report identifies four main issues:
- Data complexity and fragmentation across blockchain networks and financial sources.
- Lack of user-friendly interfaces for non-technical users.
- Limited contextual insight generation in traditional dashboards.
- Scalability and accuracy issues when answering dynamic DeFi-related queries.

### 1.3 Original objectives
The report states objectives that include:
- Developing core LLM integration.
- Implementing a user interface for natural-language interaction.
- Enabling multi-source data processing.
- Enhancing conventional analytics tools with conversational AI.

### 1.4 Important scope constraints already present in the report
Several report statements strongly support a hybrid redesign:
- The system should focus on Ethereum, Solana, and Polygon.
- It should combine structured on-chain data, off-chain market data, and unstructured text.
- It should prioritize usability and interpretability rather than automated trading.
- It should not provide financial advice.
- Historical technical indicators should be used for market prediction.
- News and social media should be used strictly for context and summaries, not as predictive features.

### 1.5 Methodology direction extracted from the report
The methodology chapter already introduces:
- A conversational LLM interface.
- A multi-layer architecture with user interaction, query interpretation, reasoning, retrieval, and output.
- A dual-stream idea separating technical quantitative analysis from qualitative summaries.
- RAG to reduce hallucination and keep insights current.

### 1.6 Limitations and future-work signals from the report
The report notes:
- Inference cost and latency remain concerns.
- Cross-chain tracking is limited.
- English-only news introduces bias.
- Future work should improve multi-protocol reasoning, robustness against manipulation, and privacy-aware deployment.

## 2. Proposed Hybrid System Design

### 2.1 System title
**LLM-based Cryptocurrency Market Insights & Query Analyzer**

### 2.2 Design principle
The proposed system follows a strict dual-stream architecture:
- **Insight Engine**: a RAG-based LLM system for explanation, retrieval, summarization, question answering, and risk narration.
- **Prediction Engine**: a separate time-series forecasting system that uses only historical structured numerical data.

The central design rule is that the LLM must never generate or infer price forecasts directly. All numerical forecasts must come only from the Prediction Engine.

### 2.3 Architectural rationale
This hybrid design resolves a key weakness in many AI-for-finance systems: using one model to perform both language reasoning and numerical forecasting. In this project, the LLM is used only where it is strong, namely contextual interpretation and explanation, while the forecasting model is used only where statistical learning on structured time-series data is appropriate. This reduces hallucination risk, improves auditability, and preserves methodological clarity.

## 3. Modular Architecture

### 3.1 High-level architecture

```text
User Query
   |
   v
[API Gateway / UI Layer]
   |
   v
[Query Understanding & Routing Layer]
   |------------------------------|
   |                              |
   v                              v
[Insight Engine]             [Prediction Engine]
   |                              |
   v                              v
[Response Composer / Guardrail Layer]
   |
   v
Final User Output
```

### 3.2 Detailed module view

```text
1. Presentation Layer
   - Web dashboard / chat UI
   - Chart and insight display

2. Orchestration Layer
   - API gateway
   - Session manager
   - Query parser
   - Intent classifier
   - Entity extractor
   - Query router

3. Insight Engine (LLM + RAG only)
   - Retrieval planner
   - Multi-source retriever
   - Document chunker / embedder
   - Vector database
   - LLM reasoning module
   - Citation and explanation generator

4. Prediction Engine (numerical model only)
   - Historical market data store
   - Feature engineering pipeline
   - Time-series model trainer
   - Forecast inference service
   - Model registry and evaluation tracker

5. Shared Governance Layer
   - Data validation
   - Access control
   - Guardrails
   - Logging and monitoring
   - Output merger
```

## 4. Data Sources

### 4.1 Insight Engine data sources
The RAG stream uses multi-source Web3 information:
- **On-chain data**: wallet transfers, token movements, DEX activity, gas usage, smart contract interactions.
- **Off-chain structured data**: OHLCV market data, exchange metrics, market dominance, volatility indicators.
- **Off-chain unstructured data**: crypto news, protocol announcements, governance posts, research reports, trusted social content.

These sources are used only for retrieval, explanation, evidence grounding, and contextual insight generation.

### 4.2 Prediction Engine data sources
The prediction stream uses only structured historical numerical data:
- Historical OHLCV prices.
- Technical indicators such as RSI, MACD, EMA, Bollinger Bands, ATR.
- On-chain numerical indicators such as active addresses, transaction count, volume, TVL, gas fees, whale transfer counts.

No news text, social sentiment text, or LLM-generated signals are allowed as prediction features.

## 5. End-to-End Data Flow

### 5.1 Stepwise flow from user query to output
1. The user submits a natural-language query through the dashboard.
2. The Query Understanding module extracts intent, asset names, chain names, time horizon, requested output type, and whether the query seeks explanation, forecast, or both.
3. The Query Router dispatches the request:
   - Insight-only queries go to the Insight Engine.
   - Prediction-only queries go to the Prediction Engine.
   - Hybrid queries trigger both streams independently.
4. In the Insight Engine:
   - Relevant sources are selected.
   - Retrieved documents and records are embedded or searched.
   - The LLM synthesizes grounded explanations from retrieved evidence only.
5. In the Prediction Engine:
   - Historical structured data is loaded.
   - Feature engineering is applied.
   - The trained time-series model generates forecast outputs and confidence-related evaluation metadata.
6. The Response Composer merges outputs while preserving separation:
   - Numerical forecast values are labeled as prediction-engine outputs.
   - Narrative interpretation is labeled as insight-engine output.
7. Guardrails verify that the final response contains no LLM-generated numeric forecasts outside the prediction stream.
8. The user receives a final response with charts, forecast tables, contextual explanation, sources, and disclaimers.

## 6. Query Routing Mechanism

### 6.1 Routing objective
The routing mechanism ensures each query is processed by the correct engine based on analytical intent. Its purpose is to preserve architectural discipline and prevent the LLM from becoming a forecasting component.

### 6.2 Query categories
- **Insight queries**: explanation, summary, event analysis, market context, on-chain interpretation, protocol comparison, risk narration.
- **Prediction queries**: next-day trend, short-term direction, volatility forecast, price range estimation, technical outlook.
- **Hybrid queries**: requests that explicitly ask for both forecast and explanation, such as "Predict ETH trend for the next 3 days and explain the current drivers."

### 6.3 Routing logic
The query router uses a lightweight classifier with rule-based safeguards:
- If the query contains forecast intents such as `predict`, `forecast`, `next day`, `next week`, `price target`, or `trend tomorrow`, route to the Prediction Engine.
- If the query requests explanation, rationale, news impact, protocol events, whale activity, or market narrative, route to the Insight Engine.
- If both intent families appear, split the query into sub-tasks and run both engines in parallel.
- If the user asks the LLM directly for a numeric prediction, the guardrail rewrites the task so the forecast request is handled only by the Prediction Engine.

### 6.4 Example routing cases

| User Query | Route | Reason |
|---|---|---|
| "Why is SOL volatile today?" | Insight Engine | Explanatory and context-seeking |
| "Predict BTC closing trend for the next 24 hours." | Prediction Engine | Pure forecasting request |
| "What happened on-chain and what is the 3-day ETH outlook?" | Both Engines | Mixed explanatory and predictive intent |

## 7. Module Responsibilities

### 7.1 Presentation Layer
- Accept user queries.
- Display charts, forecast outputs, citations, and explanations.
- Support follow-up questioning and conversation history.

### 7.2 API Gateway and Session Manager
- Authenticate requests.
- Maintain session state and conversation context.
- Pass requests to orchestration services.

### 7.3 Query Understanding Module
- Perform intent classification.
- Extract entities such as asset, chain, protocol, date range, and metric.
- Normalize user language into machine-readable task objects.

### 7.4 Query Router
- Decide whether the query is insight-only, prediction-only, or hybrid.
- Enforce separation rules between LLM reasoning and forecasting.
- Split hybrid queries into independent sub-requests.

### 7.5 Insight Engine
- Retrieve relevant on-chain, off-chain, and textual information.
- Run semantic search over indexed knowledge.
- Use the LLM to produce grounded summaries, Q&A, explanations, and risk commentary.
- Return citations and retrieved evidence.

### 7.6 Retrieval Layer
- Collect data from blockchain APIs, market APIs, and news sources.
- Clean, chunk, embed, and index unstructured documents.
- Maintain source freshness and metadata.

### 7.7 Vector Database
- Store embeddings and metadata for RAG retrieval.
- Support similarity search and filtered retrieval by asset, chain, time, and source type.

### 7.8 Prediction Engine
- Ingest historical structured time-series data.
- Generate technical and on-chain numerical features.
- Train and serve forecasting models.
- Return numerical predictions and evaluation metrics.

### 7.9 Forecasting Model Layer
Possible models include:
- LSTM or GRU for sequential temporal learning.
- Temporal Fusion Transformer for richer multivariate forecasting.
- XGBoost or LightGBM on lagged features as a strong tabular baseline.

For an FYP setting, a two-model setup is practical:
- Baseline: XGBoost on engineered lag features.
- Advanced model: LSTM or TFT for comparison.

### 7.10 Response Composer
- Merge outputs from both engines.
- Present explanation next to forecast without mixing responsibilities.
- Add visualizations such as confidence bands, feature summary, and cited evidence.

### 7.11 Guardrail and Governance Layer
- Detect forbidden behavior such as LLM-generated numeric forecasting.
- Check source provenance and timestamp freshness.
- Log decisions for reproducibility and auditability.

## 8. Engineering Specification

### 8.1 Recommended implementation stack
- **Frontend**: Streamlit for prototype speed or React for production-style modularity.
- **Backend API**: FastAPI.
- **LLM orchestration**: LangChain or LlamaIndex.
- **Vector store**: ChromaDB or FAISS.
- **Structured data store**: PostgreSQL or TimescaleDB.
- **Forecasting pipeline**: Python, pandas, scikit-learn, PyTorch.
- **Task queue**: Celery or lightweight async workers.
- **Monitoring**: MLflow for model tracking, Prometheus/Grafana for service health.

### 8.2 Data storage separation
- RAG document store for textual and retrieved evidence.
- Time-series warehouse for cleaned structured numerical datasets.
- Model registry for forecast versions and evaluation logs.

This separation is important because it prevents accidental leakage of RAG text into forecast training.

## 9. Output Format to the User

### 9.1 For insight-only output
- Natural-language answer.
- Key evidence and source citations.
- Optional summary chart or on-chain visualization.

### 9.2 For prediction-only output
- Forecasted direction or value range.
- Prediction horizon.
- Model used.
- Evaluation metrics such as RMSE, MAE, directional accuracy, or MAPE.
- Confidence note and timestamp of data cutoff.

### 9.3 For hybrid output
- **Section A: Prediction Result**
- **Section B: Insight Explanation**
- **Section C: Evidence Sources**
- **Section D: Risk and limitation note**

## 10. Academic Discussion

### 10.1 Why this architecture is suitable for the FYP
This design remains faithful to the original report because it preserves the project's emphasis on natural-language analytics, multi-source Web3 data integration, and RAG-based grounded responses. At the same time, it strengthens the methodology by formalizing the already-mentioned dual-stream concept into a strict hybrid architecture. This improves validity because numerical forecasting is delegated to dedicated time-series models rather than to a generative language model.

### 10.2 Research contribution
The proposed system contributes a clean architectural separation between:
- contextual intelligence from language models, and
- quantitative forecasting from statistical or deep time-series models.

This separation improves explainability, reduces methodological ambiguity, and aligns the system with sound AI engineering practice for financial analytics.

### 10.3 Expected benefits
- Better interpretability for non-technical users.
- Reduced hallucination risk.
- Higher trust in forecast outputs.
- Easier benchmarking and academic evaluation.
- Stronger modularity for future extension to more chains and assets.

## 11. Conclusion

The redesigned **LLM-based Cryptocurrency Market Insights & Query Analyzer** should be implemented as a strict dual-stream hybrid AI system. The **Insight Engine** should use RAG-based LLM reasoning to answer natural-language questions, summarize market developments, and explain on-chain and off-chain signals. The **Prediction Engine** should operate independently on historical structured numerical data to generate price or trend forecasts. A query-routing layer must sit between the user and both engines to classify intent, dispatch tasks, and enforce separation rules. This architecture satisfies the report's original goals while producing a more academically rigorous and engineering-ready final year project system.
