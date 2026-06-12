import os
from typing import Any

import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000"
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", DEFAULT_BACKEND_BASE_URL).rstrip("/")
REQUEST_TIMEOUT_SECONDS = 180.0

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
TIMEFRAMES = ["1h", "4h", "1d"]


class BackendApiError(RuntimeError):
    """Raised when the FastAPI backend returns an error response."""


def call_backend(method: str, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{BACKEND_BASE_URL}{path}"
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, url, json=json_body)
    except httpx.ConnectError as exc:
        raise BackendApiError(
            f"Cannot connect to backend at {BACKEND_BASE_URL}. Start FastAPI first."
        ) from exc
    except httpx.TimeoutException as exc:
        raise BackendApiError("Backend request timed out. Ollama or market data may still be loading.") from exc
    except httpx.HTTPError as exc:
        raise BackendApiError(f"Backend request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise BackendApiError(f"Backend returned non-JSON response with HTTP {response.status_code}.") from exc

    error = payload.get("error") or {}
    if response.status_code >= 400 or payload.get("success") is False:
        message = error.get("message") or response.text
        code = error.get("code")
        if code:
            raise BackendApiError(f"{code}: {message}")
        raise BackendApiError(message)

    return payload


def format_compact_number(value: Any, prefix: str = "", suffix: str = "") -> str:
    if value is None:
        return "N/A"

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    abs_number = abs(number)
    if abs_number >= 1_000_000_000_000:
        return f"{prefix}{number / 1_000_000_000_000:.2f}T{suffix}"
    if abs_number >= 1_000_000_000:
        return f"{prefix}{number / 1_000_000_000:.2f}B{suffix}"
    if abs_number >= 1_000_000:
        return f"{prefix}{number / 1_000_000:.2f}M{suffix}"
    if abs_number >= 1_000:
        return f"{prefix}{number / 1_000:.2f}K{suffix}"
    return f"{prefix}{number:.2f}{suffix}"


def format_decimal(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"

    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def render_sources(sources: list[Any]) -> None:
    if not sources:
        st.caption("No sources returned.")
        return

    for source in sources:
        if isinstance(source, dict):
            title = source.get("source_name") or source.get("source_path") or "Retrieved source"
            preview = source.get("preview")
            page = source.get("page")
            label = f"{title} (page {page})" if page is not None else title
            st.write(f"- {label}")
            if preview:
                st.caption(preview)
        else:
            st.write(f"- {source}")


def render_market_snapshot(data: dict[str, Any]) -> None:
    st.subheader("Market Snapshot")

    price_col, cap_col, volume_col, change_col = st.columns(4)
    price_col.metric("Price", format_compact_number(data.get("price"), prefix="$"))
    cap_col.metric("Market cap", format_compact_number(data.get("market_cap"), prefix="$"))
    volume_col.metric("24h volume", format_compact_number(data.get("volume_24h"), prefix="$"))
    change = data.get("change_24h_percent")
    change_col.metric("24h change", format_compact_number(change, suffix="%"))

    warnings = data.get("source_warnings") or []
    if warnings:
        st.warning("Market data source warning: " + " | ".join(warnings))


def render_indicators(data: dict[str, Any]) -> None:
    indicators = data.get("indicators") or {}
    market = data.get("market") or {}

    st.subheader("Technical Analysis")

    overview_col, trend_col = st.columns([1, 2])
    with overview_col:
        st.metric("Price", format_compact_number(data.get("price"), prefix="$"))
        st.metric("Market cap", format_compact_number(market.get("market_cap"), prefix="$"))
        st.metric("24h volume", format_compact_number(market.get("volume_24h"), prefix="$"))
        st.metric("24h change", format_compact_number(market.get("change_24h_percent"), suffix="%"))

    with trend_col:
        st.markdown("**Trend**")
        st.write(data.get("trend") or "N/A")
        st.markdown("**Risk flags**")
        for flag in data.get("risk_flags") or ["No risk flags returned."]:
            st.write(f"- {flag}")

    rsi_col, ema_col, macd_col, bollinger_col, vol_col = st.columns(5)
    rsi_col.metric("RSI", format_decimal(indicators.get("rsi"), 2))
    ema_col.metric(
        "EMA 20 / 50 / 200",
        (
            f"{format_decimal(indicators.get('ema_20'), 2)} / "
            f"{format_decimal(indicators.get('ema_50'), 2)} / "
            f"{format_decimal(indicators.get('ema_200'), 2)}"
        ),
    )
    macd_col.metric("MACD hist", format_decimal(indicators.get("macd_histogram"), 4))
    bollinger_col.metric("BB bandwidth", format_decimal(indicators.get("bollinger_bandwidth"), 4))
    vol_col.metric("Volatility 20", format_decimal(indicators.get("volatility_20"), 4))

    support_col, resistance_col = st.columns(2)
    support_col.metric("Support 20", format_decimal(indicators.get("support_20"), 2))
    resistance_col.metric("Resistance 20", format_decimal(indicators.get("resistance_20"), 2))

    with st.expander("Full indicator details"):
        st.json(indicators)

    latest_candle = data.get("latest_candle")
    if latest_candle:
        with st.expander("Latest candle"):
            st.json(latest_candle)


def render_hybrid_answer(data: dict[str, Any], api_sources: list[str]) -> None:
    st.subheader("Ollama Analysis")
    st.write(data.get("answer") or "No answer returned.")

    meta_cols = st.columns(4)
    meta_cols[0].metric("Response mode", data.get("response_mode") or data.get("generation_mode") or "N/A")
    meta_cols[1].metric("Model used", data.get("model") or "N/A")
    meta_cols[2].metric("Prompt context", data.get("prompt_context_type") or "N/A")
    meta_cols[3].metric("Fallback", "yes" if data.get("fallback_happened") else "no")

    include_parts = []
    include_parts.append(f"News: {'yes' if data.get('included_news_context') else 'no'}")
    include_parts.append(f"RAG: {'yes' if data.get('included_rag_context') else 'no'}")
    include_parts.append(f"DeFiLlama: {'yes' if data.get('included_defillama_context') else 'no'}")
    st.caption(" | ".join(include_parts))
    if data.get("selected_model") and data.get("selected_model") != data.get("model"):
        st.caption(f"Attempted Ollama model: {data.get('selected_model')}")

    context_count = data.get("retrieved_context_count")
    if context_count is not None:
        st.caption(f"Retrieved context chunks: {context_count}")

    st.markdown("**Retrieved sources**")
    render_sources(data.get("retrieved_sources") or [])

    with st.expander("Backend sources"):
        render_sources(api_sources)


def render_symbol_guardrail(data: dict[str, Any]) -> None:
    st.subheader("Symbol Guardrail")
    st.warning(data.get("message") or "The selected symbol does not match the question context.")
    st.write(f"Selected symbol: {data.get('selected_symbol') or 'N/A'}")
    st.write(f"Question symbol: {data.get('question_symbol') or 'N/A'}")
    if data.get("suggested_action"):
        st.info(data["suggested_action"])
    st.caption("No Ollama call, RAG retrieval, news lookup, or DeFiLlama context was used for this guarded request.")


def render_live_news(news_data: dict[str, Any]) -> None:
    st.subheader("Live News")

    warnings = news_data.get("warnings") or []
    for warning in warnings:
        st.caption(warning)

    articles = news_data.get("articles") or []
    if not articles:
        st.info("No live articles returned for this symbol.")
        return

    for article in articles:
        title = article.get("title") or "Untitled article"
        source = article.get("source") or article.get("provider") or "unknown source"
        published_at = article.get("published_at") or "unknown time"
        st.markdown(f"**{title}**")
        st.caption(f"{article.get('provider', 'news')} | {source} | {published_at}")
        description = article.get("description") or article.get("snippet")
        if description:
            st.write(description)
        url = article.get("url")
        if url:
            st.link_button("Open source", url)


def render_prediction(data: dict[str, Any]) -> None:
    st.subheader("Prediction Engine")

    trend = data.get("predicted_trend") or "N/A"
    probability_up = data.get("probability_up")
    probability_down = data.get("probability_down")
    metrics = data.get("metrics") or {}

    trend_col, up_col, down_col, model_col = st.columns(4)
    trend_col.metric("Predicted trend", trend)
    up_col.metric("Probability UP", format_compact_number(probability_up, suffix=""))
    down_col.metric("Probability DOWN", format_compact_number(probability_down, suffix=""))
    model_col.metric("Model", data.get("model_name") or "N/A")
    horizon_value = data.get("horizon_candles") or data.get("horizon_days") or "N/A"
    st.caption(f"Horizon: {data.get('horizon_label') or f'future {horizon_value} candles'}")

    if metrics:
        metric_cols = st.columns(4)
        metric_cols[0].metric("Accuracy", format_decimal(metrics.get("accuracy"), 4))
        metric_cols[1].metric("Precision", format_decimal(metrics.get("precision"), 4))
        metric_cols[2].metric("Recall", format_decimal(metrics.get("recall"), 4))
        metric_cols[3].metric("F1", format_decimal(metrics.get("f1"), 4))
        st.caption(f"Metric type: {metrics.get('metric_type', 'demo_backtest')}")
        baseline = metrics.get("baseline") or {}
        st.write(
            "Baseline comparison: "
            f"model={format_decimal(metrics.get('model_accuracy'), 4)}, "
            f"baseline={format_decimal(metrics.get('baseline_accuracy') or baseline.get('baseline_accuracy'), 4)}, "
            f"improvement={format_decimal(metrics.get('model_vs_baseline_improvement'), 4)}"
        )
        confusion = metrics.get("confusion_matrix") or {}
        if confusion.get("matrix"):
            st.markdown("**Confusion matrix**")
            st.dataframe(
                pd.DataFrame(confusion["matrix"], index=confusion.get("labels", ["DOWN", "UP"]), columns=confusion.get("labels", ["DOWN", "UP"]))
            )
        if metrics.get("support"):
            st.markdown("**Class support**")
            st.json(metrics["support"])
        st.write(f"85% target achieved: {metrics.get('target_85_achieved')}")
    else:
        st.info("Model metrics are not available for this run. The backend used a transparent fallback.")

    evaluation = data.get("evaluation") or {}
    if evaluation:
        st.markdown("**Interpretation**")
        st.write(evaluation.get("summary") or "No interpretation summary returned.")
        st.caption(evaluation.get("reliability") or "")
    if data.get("sample_warning"):
        st.warning(data["sample_warning"])

    features = data.get("features") or []
    if features:
        st.markdown("**Features used**")
        st.write(", ".join(features))

    notes = data.get("notes") or []
    for note in notes:
        st.caption(note)

    chart_data = data.get("chart_data") or []
    if chart_data:
        chart_frame = pd.DataFrame(chart_data)
        chart_frame["timestamp"] = pd.to_datetime(chart_frame["timestamp"], errors="coerce")
        chart_frame = chart_frame.dropna(subset=["timestamp"]).set_index("timestamp")

        st.subheader("Visualisation")
        st.line_chart(chart_frame[["close"]])
        st.line_chart(chart_frame[["rsi"]])

    st.warning(data.get("disclaimer") or "This prediction is for academic demonstration only and is not financial advice.")


def main() -> None:
    st.set_page_config(page_title="Backend Functional Test Console", layout="wide")
    st.title("Backend Functional Test Console")
    st.caption(
        "Testing and fallback UI for FastAPI endpoints. Use the polished React UI for final demo screenshots and presentation."
    )

    with st.sidebar:
        st.markdown("### Purpose")
        st.info("Use this Streamlit console to verify backend functions quickly. It does not contain separate prediction or RAG logic.")
        st.markdown("### Backend")
        st.code(BACKEND_BASE_URL)
        if st.button("Check backend health"):
            try:
                with st.spinner("Checking backend..."):
                    health_payload = call_backend("GET", "/health")
                st.success("Backend is reachable.")
                st.json(health_payload.get("data", {}))
            except BackendApiError as exc:
                st.error(str(exc))

        st.markdown("### Query")
        symbol = st.selectbox("Symbol", SYMBOLS, index=0)
        timeframe = st.selectbox("Timeframe", TIMEFRAMES, index=0)
        limit = st.slider("Candle limit", min_value=50, max_value=300, value=120, step=10)
        horizon_days = st.slider("Prediction horizon", min_value=1, max_value=14, value=3, step=1)

    question = st.text_area(
        "Ask a market question",
        value="Why is BTC moving today and what is the short-term risk?",
        height=110,
    )

    market_tab, basic_tab, hybrid_tab, live_news_tab, prediction_tab = st.tabs(
        ["GET /market", "POST /analyze-basic", "POST /analyze", "GET /news", "POST /predict"]
    )

    with market_tab:
        if st.button("Load market snapshot", type="primary"):
            try:
                with st.spinner("Fetching Binance and CoinGecko market data..."):
                    payload = call_backend("GET", f"/market/{symbol}")
                render_market_snapshot(payload.get("data") or {})
                with st.expander("Sources"):
                    render_sources(payload.get("sources") or [])
            except BackendApiError as exc:
                st.error(str(exc))

    with basic_tab:
        if st.button("Run basic technical analysis", type="primary"):
            body = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
            try:
                with st.spinner("Fetching candles and calculating indicators..."):
                    payload = call_backend("POST", "/analyze-basic", body)
                render_indicators(payload.get("data") or {})
                with st.expander("Sources"):
                    render_sources(payload.get("sources") or [])
            except BackendApiError as exc:
                st.error(str(exc))

    with hybrid_tab:
        disabled = not question.strip()
        if st.button("Run hybrid analysis", type="primary", disabled=disabled):
            body = {
                "symbol": symbol,
                "timeframe": timeframe,
                "limit": limit,
                "question": question.strip(),
            }
            try:
                with st.spinner("Running market analysis, RAG retrieval, and Ollama generation..."):
                    payload = call_backend("POST", "/analyze", body)
                data = payload.get("data") or {}
                if data.get("guardrail_triggered"):
                    render_symbol_guardrail(data)
                else:
                    render_indicators(data)
                    render_hybrid_answer(data, payload.get("sources") or [])
                    render_live_news(data.get("live_news") or {})
            except BackendApiError as exc:
                st.error(str(exc))

        if disabled:
            st.info("Enter a question before running hybrid analysis.")

    with live_news_tab:
        if st.button("Load live news", type="primary"):
            try:
                with st.spinner("Fetching Marketaux and GNews articles..."):
                    payload = call_backend("GET", f"/news/{symbol}?limit=6")
                render_live_news(payload.get("data") or {})
                with st.expander("Sources"):
                    render_sources(payload.get("sources") or [])
            except BackendApiError as exc:
                st.error(str(exc))

    with prediction_tab:
        if st.button("Run prediction", type="primary"):
            body = {
                "symbol": symbol,
                "timeframe": timeframe,
                "horizon_candles": horizon_days,
                "limit": max(limit, 300 if timeframe == "1d" else 120),
            }
            try:
                with st.spinner("Fetching OHLCV data, calculating indicators, and running trend classification..."):
                    payload = call_backend("POST", "/predict", body)
                render_prediction(payload.get("data") or {})
                with st.expander("Sources"):
                    render_sources(payload.get("sources") or [])
            except BackendApiError as exc:
                st.error(str(exc))


if __name__ == "__main__":
    main()
