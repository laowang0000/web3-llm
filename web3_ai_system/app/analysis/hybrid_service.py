import json
import re
from typing import Any

from app.defi_data.defillama_client import DefiLlamaClient, DefiLlamaClientError, defillama_context_enabled
from app.insight_engine.pdf_evidence import (
    chunk_metadata as pdf_chunk_metadata,
    format_documents_context as format_pdf_context,
    retrieve_explicit_pdf_documents,
    source_labels as pdf_source_labels,
)
from app.insight_engine.service import InsightService
from app.llm.ollama_client import OllamaChatClient, OllamaClientError
from app.market_data.service import MarketDataService
from app.news_data.service import LiveNewsService
from app.utils.logging import get_logger


logger = get_logger(__name__)

TECHNICAL_KEYWORDS = (
    "rsi",
    "ema",
    "macd",
    "bollinger",
    "volatility",
    "momentum",
    "technical trend",
    "technical analysis",
    "overbought",
    "oversold",
    "moving average",
    "support",
    "resistance",
)

NEWS_KEYWORDS = (
    "news",
    "headlines",
    "gnews",
    "marketaux",
    "sentiment",
    "recent",
    "latest",
    "today",
    "market narrative",
    "narrative",
    "catalyst",
)

RAG_KEYWORDS = (
    "rag",
    "paper",
    "document",
    "documents",
    "report",
    "whitepaper",
    "uploaded knowledge",
    "literature",
    "source-grounded",
    "retrieved context",
)

DEFILLAMA_KEYWORDS = (
    "defillama",
    "tvl",
    "protocol",
    "chain",
    "ecosystem",
    "defi",
    "liquidity",
    "on-chain",
    "onchain",
)

BROAD_CONTEXT_KEYWORDS = (
    "full market risk analysis",
    "full risk analysis",
    "full context",
    "full available context",
    "all available context",
    "comprehensive",
    "complete market",
    "broad market",
    "technical indicators, news, rag",
)


class HybridAnalysisServiceError(RuntimeError):
    """Raised when hybrid market analysis cannot be completed."""


class HybridAnalysisService:
    def __init__(
        self,
        market_service: MarketDataService | None = None,
        insight_service: InsightService | None = None,
        news_service: LiveNewsService | None = None,
        llm_client: Any | None = None,
        defillama_client: DefiLlamaClient | None = None,
    ) -> None:
        self.market_service = market_service or MarketDataService()
        self._insight_service = insight_service
        self._news_service = news_service
        self.llm = llm_client or OllamaChatClient()
        self._defillama = defillama_client

    @property
    def insight_service(self) -> InsightService:
        if self._insight_service is None:
            self._insight_service = InsightService()
        return self._insight_service

    @property
    def news_service(self) -> LiveNewsService:
        if self._news_service is None:
            self._news_service = LiveNewsService()
        return self._news_service

    @property
    def defillama(self) -> DefiLlamaClient:
        if self._defillama is None:
            self._defillama = DefiLlamaClient()
        return self._defillama

    def analyze(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        question: str,
        selected_model: str | None = None,
    ) -> tuple[dict[str, Any], list[str]]:
        market_data, market_sources = self.market_service.analyze_basic(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        context_strategy = self._select_context_strategy(question)
        compact_technical = context_strategy["prompt_context_type"] == "technical_compact"
        documents = []
        rag_sources: list[str] = []
        retrieved_metadata: list[dict[str, Any]] = []
        news_data = self._empty_news_data(market_data["symbol"])
        news_sources: list[str] = []
        news_source_labels: list[str] = []
        defi_context: dict[str, Any] | None = None
        defillama_status = "not_requested"
        defillama_warning = None
        included_rag_context = False
        included_news_context = False
        included_defillama_context = False
        rag_warning: str | None = None

        if compact_technical:
            prompt_context = self._build_technical_prompt_context(market_data, limit)
            prompt_context_type = context_strategy["prompt_context_type"]
            system_prompt = self._technical_system_prompt()
            success_response_mode = context_strategy["response_mode"]
        else:
            rag_context = ""
            if context_strategy["include_rag"]:
                retrieval_query = self._build_retrieval_query(market_data, question)
                explicit_pdf_documents = retrieve_explicit_pdf_documents(retrieval_query)
                vector_documents = []
                try:
                    vector_documents = self.insight_service.retrieve(retrieval_query)
                except Exception as exc:
                    rag_warning = f"Vector RAG retrieval unavailable: {exc}"
                    if not explicit_pdf_documents:
                        raise
                documents = self._merge_documents(explicit_pdf_documents, vector_documents)
                rag_context = self._clip_context(self._format_retrieved_context(documents), 1800)
                rag_sources = self._source_labels(documents)
                retrieved_metadata = self._chunk_metadata(documents)
                included_rag_context = bool(rag_context)

            news_context = ""
            if context_strategy["include_news"]:
                news_data, news_sources = self.news_service.fetch_relevant_news(
                    symbol=market_data["symbol"],
                    question=question,
                )
                news_context = self._clip_context(self.news_service.format_context(news_data), 500)
                news_source_labels = self.news_service.source_labels(news_data)
                included_news_context = bool(news_data.get("article_count"))

            if context_strategy["include_defillama"]:
                defi_context, defillama_status, defillama_warning = self._fetch_defi_context(market_data["symbol"])
                included_defillama_context = defillama_status == "available"

            prompt_context = self._build_prompt_context(
                market_data,
                defi_context,
                rag_context,
                news_context,
                include_defillama=context_strategy["include_defillama"],
                include_rag=context_strategy["include_rag"],
                include_news=context_strategy["include_news"],
            )
            prompt_context_type = context_strategy["prompt_context_type"]
            system_prompt = self._system_prompt()
            success_response_mode = context_strategy["response_mode"]

        fallback_happened = False
        llm_client = self.llm.with_model(selected_model) if selected_model else self.llm
        model_requested = llm_client.settings.model
        try:
            answer = llm_client.chat(
                message=question,
                system_prompt=system_prompt,
                context=prompt_context,
            )
            model_name = model_requested
            generation_mode = "ollama"
            response_mode = success_response_mode
        except OllamaClientError as exc:
            answer = self._fallback_answer(market_data, news_data, defi_context, defillama_status, str(exc))
            model_name = "backend-structured-fallback"
            generation_mode = "backend_fallback"
            response_mode = "structured_fallback"
            fallback_happened = True

        data = {
            "symbol": market_data["symbol"],
            "provider": market_data.get("provider"),
            "market_provider": market_data.get("provider"),
            "timeframe": market_data["timeframe"],
            "price": market_data["price"],
            "price_usd": market_data.get("price_usd"),
            "indicators": market_data["indicators"],
            "trend": market_data["trend"],
            "risk_flags": market_data["risk_flags"],
            "answer": answer,
            "analysis": answer,
            "model": model_name,
            "model_used": model_name,
            "selected_model": model_requested,
            "llm_model": model_requested,
            "generation_mode": generation_mode,
            "response_mode": response_mode,
            "prompt_context_type": prompt_context_type,
            "news_context_included": included_news_context,
            "rag_context_included": included_rag_context,
            "defillama_context_included": included_defillama_context,
            "included_news_context": included_news_context,
            "included_rag_context": included_rag_context,
            "included_defillama_context": included_defillama_context,
            "fallback_happened": fallback_happened,
            "defillama_status": defillama_status,
            "defi_context": defi_context,
            "retrieved_context_count": len(documents),
            "retrieved_sources": retrieved_metadata,
            "live_news": news_data,
            "live_news_count": news_data.get("article_count", 0),
            "live_news_warnings": news_data.get("warnings", []),
            "market": market_data.get("market", {}),
            "latest_candle": market_data.get("latest_candle", {}),
            "source_warnings": market_data.get("source_warnings", []),
            "data_mode": market_data.get("data_mode", "live"),
        }
        if defillama_warning:
            data["source_warnings"] = [*data["source_warnings"], defillama_warning]
        if rag_warning:
            data["source_warnings"] = [*data["source_warnings"], rag_warning]
        sources = list(
            dict.fromkeys(
                market_sources
                + (["defillama"] if defillama_status == "available" else [])
                + rag_sources
                + news_sources
                + news_source_labels
            )
        )
        self._log_analysis_route(
            selected_model=model_requested,
            response_mode=response_mode,
            prompt_context_type=prompt_context_type,
            included_news_context=included_news_context,
            included_rag_context=included_rag_context,
            included_defillama_context=included_defillama_context,
            fallback_happened=fallback_happened,
        )
        return data, sources

    def _select_context_strategy(self, question: str) -> dict[str, Any]:
        normalized_question = self._normalize_question(question)
        has_technical_keyword = self._contains_any(normalized_question, TECHNICAL_KEYWORDS)
        wants_broad_context = self._contains_any(normalized_question, BROAD_CONTEXT_KEYWORDS)
        include_news = wants_broad_context or self._contains_any(normalized_question, NEWS_KEYWORDS)
        include_rag = wants_broad_context or self._contains_any(normalized_question, RAG_KEYWORDS)
        include_defillama = wants_broad_context or self._contains_any(normalized_question, DEFILLAMA_KEYWORDS)

        if has_technical_keyword and not any((include_news, include_rag, include_defillama)):
            return {
                "include_news": False,
                "include_rag": False,
                "include_defillama": False,
                "prompt_context_type": "technical_compact",
                "response_mode": "technical_llm_compact_context",
            }

        if wants_broad_context:
            return {
                "include_news": True,
                "include_rag": True,
                "include_defillama": True,
                "prompt_context_type": "broad_full_context",
                "response_mode": "broad_llm_full_context",
            }

        if not any((include_news, include_rag, include_defillama)):
            return {
                "include_news": False,
                "include_rag": False,
                "include_defillama": False,
                "prompt_context_type": "technical_compact",
                "response_mode": "technical_llm_compact_context",
            }

        selected_contexts = [
            label
            for label, included in (
                ("news", include_news),
                ("rag", include_rag),
                ("defillama", include_defillama),
            )
            if included
        ]
        context_label = "_".join(selected_contexts)
        return {
            "include_news": include_news,
            "include_rag": include_rag,
            "include_defillama": include_defillama,
            "prompt_context_type": f"{context_label}_context",
            "response_mode": f"{context_label}_llm_context",
        }

    def _contains_any(self, normalized_question: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in normalized_question for keyword in keywords)

    def _normalize_question(self, question: str) -> str:
        return re.sub(r"\s+", " ", question.strip().lower())

    def _empty_news_data(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "query": {},
            "articles": [],
            "article_count": 0,
            "warnings": [],
        }

    def _build_retrieval_query(self, market_data: dict[str, Any], question: str) -> str:
        return (
            f"{question}\n"
            f"Symbol: {market_data['symbol']}\n"
            f"Trend: {market_data['trend']}\n"
            f"Risk flags: {'; '.join(market_data['risk_flags'])}"
        )

    def _merge_documents(self, preferred_documents: list[Any], vector_documents: list[Any]) -> list[Any]:
        merged: list[Any] = []
        seen: set[tuple[str, Any]] = set()
        for doc in [*preferred_documents, *vector_documents]:
            metadata = getattr(doc, "metadata", {}) or {}
            key = (str(metadata.get("source_name") or metadata.get("source_path") or ""), metadata.get("page"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(doc)
        return merged

    def _format_retrieved_context(self, documents: list[Any]) -> str:
        explicit_pdf_documents = [
            doc
            for doc in documents
            if (getattr(doc, "metadata", {}) or {}).get("retrieval_mode") == "explicit_pdf"
        ]
        remaining_documents = [doc for doc in documents if doc not in explicit_pdf_documents]
        blocks: list[str] = []
        if explicit_pdf_documents:
            blocks.append(format_pdf_context(explicit_pdf_documents))
        if remaining_documents:
            blocks.append(self.insight_service.format_context(remaining_documents))
        return "\n\n".join(blocks)

    def _source_labels(self, documents: list[Any]) -> list[str]:
        explicit_pdf_documents = [
            doc
            for doc in documents
            if (getattr(doc, "metadata", {}) or {}).get("retrieval_mode") == "explicit_pdf"
        ]
        remaining_documents = [doc for doc in documents if doc not in explicit_pdf_documents]
        labels = pdf_source_labels(explicit_pdf_documents)
        if remaining_documents:
            labels.extend(self.insight_service.source_labels(remaining_documents))
        return labels

    def _chunk_metadata(self, documents: list[Any]) -> list[dict[str, Any]]:
        explicit_pdf_documents = [
            doc
            for doc in documents
            if (getattr(doc, "metadata", {}) or {}).get("retrieval_mode") == "explicit_pdf"
        ]
        remaining_documents = [doc for doc in documents if doc not in explicit_pdf_documents]
        metadata = pdf_chunk_metadata(explicit_pdf_documents)
        if remaining_documents:
            metadata.extend(self.insight_service.chunk_metadata(remaining_documents))
        return metadata

    def _fetch_defi_context(self, symbol: str) -> tuple[dict[str, Any] | None, str, str | None]:
        if not defillama_context_enabled():
            return None, "disabled", None
        try:
            context = self.defillama.build_symbol_context(symbol)
        except DefiLlamaClientError as exc:
            warning = f"DeFiLlama context unavailable: {exc}"
            print(f"[defillama] {warning}")
            return None, "unavailable", warning
        if context is None:
            return None, "not_applicable", None
        return context, "available", None

    def _build_prompt_context(
        self,
        market_data: dict[str, Any],
        defi_context: dict[str, Any] | None,
        rag_context: str,
        news_context: str,
        *,
        include_defillama: bool,
        include_rag: bool,
        include_news: bool,
    ) -> str:
        indicators = market_data["indicators"]
        market_payload = {
            "symbol": market_data["symbol"],
            "provider": market_data.get("provider"),
            "source": market_data.get("source"),
            "timestamp": market_data.get("timestamp"),
            "timeframe": market_data["timeframe"],
            "latest_price": market_data["price"],
            "change_24h_percent": (market_data.get("market") or {}).get("change_24h_percent"),
            "volume_24h_usd": (market_data.get("market") or {}).get("volume_24h_usd"),
            "latest_candle": market_data.get("latest_candle", {}),
            "indicators": {
                "rsi": indicators.get("rsi"),
                "ema_12": indicators.get("ema_12"),
                "ema_20": indicators.get("ema_20"),
                "ema_26": indicators.get("ema_26"),
                "ema_50": indicators.get("ema_50"),
                "ema_200": indicators.get("ema_200"),
                "macd": indicators.get("macd"),
                "macd_signal": indicators.get("macd_signal"),
                "macd_histogram": indicators.get("macd_histogram"),
                "bollinger_upper": indicators.get("bollinger_upper"),
                "bollinger_middle": indicators.get("bollinger_middle"),
                "bollinger_lower": indicators.get("bollinger_lower"),
                "bollinger_bandwidth": indicators.get("bollinger_bandwidth"),
                "volatility_20": indicators.get("volatility_20"),
                "support_20": indicators.get("support_20"),
                "resistance_20": indicators.get("resistance_20"),
            },
            "trend_summary": market_data["trend"],
            "risk_flags": market_data["risk_flags"],
        }
        context_blocks = [
            "Market data and technical indicators:\n"
            f"{json.dumps(market_payload, indent=2)}"
        ]
        if include_defillama:
            defi_payload = defi_context or {
                "status": "not_available",
                "note": "No safe DeFiLlama chain or protocol mapping was available for this symbol.",
            }
            context_blocks.append(
                "DeFiLlama DeFi ecosystem context:\n"
                f"{json.dumps(defi_payload, indent=2)}"
            )
        if include_rag:
            retrieved_context = rag_context or "No relevant RAG context was retrieved."
            context_blocks.append(f"Retrieved RAG context:\n{retrieved_context}")
        if include_news:
            live_news_context = news_context or "No live news articles were retrieved."
            context_blocks.append(f"Live news context:\n{live_news_context}")
        return "\n\n".join(context_blocks)

    def _build_technical_prompt_context(self, market_data: dict[str, Any], limit: int) -> str:
        indicators = market_data["indicators"]
        compact_payload = {
            "symbol": market_data["symbol"],
            "source": market_data.get("source"),
            "provider": market_data.get("provider"),
            "timestamp": market_data.get("timestamp"),
            "timeframe": market_data["timeframe"],
            "limit": limit,
            "latest_close_price": indicators.get("close") or market_data.get("price"),
            "change_24h_percent": (market_data.get("market") or {}).get("change_24h_percent"),
            "volume_24h_usd": (market_data.get("market") or {}).get("volume_24h_usd"),
            "rsi": {
                "value": indicators.get("rsi"),
                "hint": self._rsi_hint(indicators.get("rsi")),
            },
            "ema_trend": {
                "ema_20": indicators.get("ema_20"),
                "ema_50": indicators.get("ema_50"),
                "ema_200": indicators.get("ema_200"),
                "hint": self._ema_hint(indicators),
            },
            "macd": {
                "value": indicators.get("macd"),
                "signal": indicators.get("macd_signal"),
                "histogram": indicators.get("macd_histogram"),
                "hint": self._macd_hint(indicators.get("macd_histogram")),
            },
            "bollinger_volatility": {
                "upper": indicators.get("bollinger_upper"),
                "middle": indicators.get("bollinger_middle"),
                "lower": indicators.get("bollinger_lower"),
                "bandwidth": indicators.get("bollinger_bandwidth"),
                "volatility_20": indicators.get("volatility_20"),
                "hint": self._bollinger_volatility_hint(indicators),
            },
            "support_resistance": {
                "support_20": indicators.get("support_20"),
                "resistance_20": indicators.get("resistance_20"),
            },
            "trend_summary": market_data["trend"],
            "risk_flags": market_data["risk_flags"],
        }
        return json.dumps(compact_payload, indent=2)

    def _technical_system_prompt(self) -> str:
        return (
            "You are a professional Web3 and crypto market risk analyst for an academic FYP system. "
            "Use only the compact technical indicator context provided. Do not invent live data, sources, PDF names, "
            "page numbers, or indicators. Output exactly these sections: 1. Executive Summary, 2. Live Market Data, "
            "3. Technical Indicators, 4. RAG/PDF Evidence, 5. Analysis, 6. Risk Conclusion. "
            "In Executive Summary include current price, 24h change, market direction "
            "(bullish, bearish, neutral, or volatile), main risk driver, and confidence. "
            "In Live Market Data include source, timestamp, price, 24h change, and volume if available; write "
            "Evidence missing when a field is absent. In Technical Indicators include RSI, EMA 20 / EMA 50 / EMA 200 "
            "if available, Bollinger Bands if available, and support/resistance if available. "
            "RSI rules: RSI > 70 = overbought; RSI < 30 = oversold; RSI 30-40 = weak momentum / near oversold, "
            "but not oversold; RSI 40-60 = neutral; RSI 60-70 = strong momentum / near overbought, but not overbought. "
            "EMA rules: price below short-term EMA suggests weak short-term momentum; bearish EMA alignment suggests "
            "downside risk; bullish EMA alignment suggests upward momentum. Bollinger rule: price near the lower band "
            "may indicate support or downside pressure, never a guaranteed buy signal. "
            "In RAG/PDF Evidence write exactly: No relevant PDF evidence was retrieved, so this analysis is not fully RAG-grounded. "
            "Separate facts from interpretation in Analysis. Never claim certainty; use cautious wording such as suggests, "
            "may indicate, appears, risk remains, and confidence is limited. "
            "End with: This is a market risk analysis, not financial advice."
        )

    def _system_prompt(self) -> str:
        return (
            "You are a professional Web3 and crypto market risk analyst for an academic FYP MVP. "
            "Use only the provided market data, technical indicators, risk flags, DeFiLlama context, retrieved RAG context, "
            "and live news context. Do not invent live data, sources, PDF names, page numbers, technical indicators, or retrieved claims. "
            "Output exactly these sections: 1. Executive Summary, 2. Live Market Data, 3. Technical Indicators, "
            "4. RAG/PDF Evidence, 5. Analysis, 6. Risk Conclusion. "
            "Executive Summary must include current price, 24h change, market direction "
            "(bullish, bearish, neutral, or volatile), main risk driver, and confidence (Low, Medium, or High). "
            "Live Market Data must include source, timestamp, price, 24h change, and volume if available; write Evidence missing "
            "when a field is absent. Technical Indicators must include RSI, EMA 20 / EMA 50 / EMA 200 if available, "
            "Bollinger Bands if available, and support/resistance if available. "
            "RSI rules: RSI > 70 = overbought; RSI < 30 = oversold; RSI 30-40 = weak momentum / near oversold, but not oversold; "
            "RSI 40-60 = neutral; RSI 60-70 = strong momentum / near overbought, but not overbought. "
            "EMA rules: price below short-term EMA suggests weak short-term momentum; bearish EMA alignment suggests downside risk; "
            "bullish EMA alignment suggests upward momentum. Bollinger rule: price near the lower band may indicate support or "
            "downside pressure, never a guaranteed buy signal. "
            "For every retrieved PDF/RAG source, cite PDF name, page number, retrieved claim, why it matters, and risk implication "
            "(bullish, bearish, neutral, or structural). If no relevant PDF evidence was retrieved, write exactly: "
            "No relevant PDF evidence was retrieved, so this analysis is not fully RAG-grounded. "
            "Do not say source-grounded unless PDF evidence is shown by name and page. Do not use vague phrases like based on documents "
            "without naming the document. DeFiLlama context reflects ecosystem health, TVL, liquidity, and protocol fundamentals; "
            "it is not direct price prediction data. Separate facts from interpretation in Analysis. Never claim certainty; use cautious "
            "wording such as suggests, may indicate, appears, risk remains, and confidence is limited. "
            "Do not provide price targets, guaranteed predictions, trading advice, or unsupported causal claims. "
            "End with: This is a market risk analysis, not financial advice."
        )

    def _clip_context(self, value: str, max_length: int) -> str:
        text = " ".join((value or "").split())
        if len(text) <= max_length:
            return text
        return f"{text[: max_length - 3]}..."

    def _rsi_hint(self, value: Any) -> str:
        rsi = self._optional_float(value)
        if rsi is None:
            return "RSI unavailable."
        if rsi > 70:
            return "Overbought; upside momentum may be stretched."
        if rsi < 30:
            return "Oversold; downside momentum may be stretched."
        if rsi >= 60:
            return "Strong momentum / near overbought, but not overbought."
        if rsi <= 40:
            return "Weak momentum / near oversold, but not oversold."
        return "Neutral momentum zone."

    def _ema_hint(self, indicators: dict[str, Any]) -> str:
        close = self._optional_float(indicators.get("close"))
        ema_20 = self._optional_float(indicators.get("ema_20"))
        ema_50 = self._optional_float(indicators.get("ema_50"))
        ema_200 = self._optional_float(indicators.get("ema_200"))
        if close is None or ema_20 is None or ema_50 is None:
            return "EMA trend unavailable."
        if ema_200 is not None and close > ema_20 > ema_50 > ema_200:
            return "Price is above EMA20 and EMA20 > EMA50 > EMA200; bullish EMA alignment suggests upward momentum."
        if ema_200 is not None and close < ema_20 < ema_50 < ema_200:
            return "Price is below EMA20 and EMA20 < EMA50 < EMA200; bearish EMA alignment suggests downside risk."
        if close > ema_20 > ema_50:
            return "Price is above EMA20 and EMA20 is above EMA50; bullish short-term EMA alignment suggests upward momentum."
        if close < ema_20 < ema_50:
            return "Price is below EMA20 and EMA20 is below EMA50; bearish short-term EMA alignment suggests downside risk."
        if close > ema_20:
            return "Price is above EMA20 but EMA alignment is mixed."
        if close < ema_20:
            return "Price is below EMA20, which suggests weak short-term momentum, but EMA alignment is mixed."
        return "Price is near EMA20; trend structure is neutral."

    def _macd_hint(self, value: Any) -> str:
        histogram = self._optional_float(value)
        if histogram is None:
            return "MACD histogram unavailable."
        if histogram > 0:
            return "Positive histogram; momentum is above the MACD signal line."
        if histogram < 0:
            return "Negative histogram; momentum is below the MACD signal line."
        return "Histogram is near zero; MACD momentum is neutral."

    def _bollinger_volatility_hint(self, indicators: dict[str, Any]) -> str:
        close = self._optional_float(indicators.get("close"))
        upper = self._optional_float(indicators.get("bollinger_upper"))
        lower = self._optional_float(indicators.get("bollinger_lower"))
        bandwidth = self._optional_float(indicators.get("bollinger_bandwidth"))
        volatility = self._optional_float(indicators.get("volatility_20"))
        hints: list[str] = []
        if close is not None and upper is not None and lower is not None:
            if close >= upper:
                hints.append("Price is near or above the upper Bollinger Band.")
            elif close <= lower:
                hints.append("Price is near or below the lower Bollinger Band, which may indicate support or downside pressure but is not a guaranteed buy signal.")
            else:
                hints.append("Price is inside the Bollinger Bands.")
        if bandwidth is not None:
            hints.append("Bollinger bandwidth is elevated." if bandwidth >= 0.08 else "Bollinger bandwidth is not elevated.")
        if volatility is not None:
            hints.append("20-candle volatility is elevated." if volatility >= 0.04 else "20-candle volatility is not elevated.")
        return " ".join(hints) if hints else "Bollinger and volatility context unavailable."

    def _optional_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _log_analysis_route(
        self,
        *,
        selected_model: str,
        response_mode: str,
        prompt_context_type: str,
        included_news_context: bool,
        included_rag_context: bool,
        included_defillama_context: bool,
        fallback_happened: bool,
    ) -> None:
        logger.info(
            "analyze route selected_model=%s response_mode=%s prompt_context_type=%s "
            "included_news=%s included_rag=%s included_defillama=%s fallback=%s",
            selected_model,
            response_mode,
            prompt_context_type,
            included_news_context,
            included_rag_context,
            included_defillama_context,
            fallback_happened,
        )

    def _fallback_answer(
        self,
        market_data: dict[str, Any],
        news_data: dict[str, Any],
        defi_context: dict[str, Any] | None,
        defillama_status: str,
        reason: str,
    ) -> str:
        warnings = market_data.get("source_warnings") or []
        news_count = news_data.get("article_count", 0)
        risk_flags = market_data.get("risk_flags") or ["No risk flags returned."]
        main_risk_driver = risk_flags[0]
        defi_summary = self._defi_fallback_summary(defi_context, defillama_status)
        news_summary = self._fallback_news_summary(news_data)
        indicators = market_data.get("indicators") or {}
        rsi = indicators.get("rsi")
        rsi_hint = self._rsi_hint(rsi)
        ema_20 = indicators.get("ema_20")
        ema_50 = indicators.get("ema_50")
        ema_200 = indicators.get("ema_200")
        bollinger_upper = indicators.get("bollinger_upper")
        bollinger_middle = indicators.get("bollinger_middle")
        bollinger_lower = indicators.get("bollinger_lower")
        support_20 = indicators.get("support_20")
        resistance_20 = indicators.get("resistance_20")
        market = market_data.get("market") or {}
        direction = self._market_direction(market_data)
        final_risk_level = self._risk_level(risk_flags)
        return (
            "1. Executive Summary\n\n"
            f"* Current price: {self._format_evidence_metric(market_data.get('price'))}\n"
            f"* 24h change: {self._format_percent(market.get('change_24h_percent'))}\n"
            f"* Market direction: {direction}\n"
            f"* Main risk driver: {main_risk_driver}\n"
            "* Confidence: Low\n\n"
            "2. Live Market Data\n\n"
            f"* Source: {market_data.get('source') or market_data.get('provider') or 'Evidence missing'}\n"
            f"* Timestamp: {market_data.get('timestamp') or 'Evidence missing'}\n"
            f"* Price: {self._format_evidence_metric(market_data.get('price'))}\n"
            f"* 24h change: {self._format_percent(market.get('change_24h_percent'))}\n"
            f"* Volume if available: {self._format_evidence_metric(market.get('volume_24h_usd'))}\n\n"
            "3. Technical Indicators\n\n"
            f"* RSI: {self._format_optional_metric(rsi)} ({rsi_hint})\n"
            f"* EMA 20 / EMA 50 / EMA 200: {self._format_optional_metric(ema_20)} / "
            f"{self._format_optional_metric(ema_50)} / {self._format_optional_metric(ema_200)} "
            f"({self._ema_hint(indicators)})\n"
            f"* Bollinger Bands: upper {self._format_optional_metric(bollinger_upper)}, "
            f"middle {self._format_optional_metric(bollinger_middle)}, "
            f"lower {self._format_optional_metric(bollinger_lower)} "
            f"({self._bollinger_volatility_hint(indicators)})\n"
            f"* Support and resistance: support {self._format_optional_metric(support_20)}, "
            f"resistance {self._format_optional_metric(resistance_20)}\n\n"
            "4. RAG/PDF Evidence\n\n"
            "No relevant PDF evidence was retrieved, so this analysis is not fully RAG-grounded.\n\n"
            "5. Analysis\n\n"
            "Facts: The backend used live market data and calculated technical indicators from real OHLCV candles. "
            f"Retrieved live news count was {news_count}. DeFiLlama context status was {defi_summary}. "
            f"Provider warnings: {' | '.join(warnings) if warnings else 'none'}.\n\n"
            "Interpretation: The risk view appears mainly driven by the listed technical risk flags. "
            "Because the local LLM did not complete, confidence is limited and the analysis avoids unsupported causal claims. "
            f"Live news evidence summary: {news_summary}\n\n"
            "6. Risk Conclusion\n\n"
            f"Final risk level: {final_risk_level}\n"
            "Confidence: Low\n"
            f"Fallback reason: {reason}\n\n"
            "This is a market risk analysis, not financial advice."
        )

    def _fallback_news_summary(self, news_data: dict[str, Any]) -> str:
        articles = news_data.get("articles") or []
        if not articles:
            warnings = news_data.get("warnings") or []
            warning_text = f" Warnings: {' | '.join(warnings)}." if warnings else ""
            return f"No live news articles were retrieved.{warning_text}"

        parts: list[str] = []
        for index, article in enumerate(articles[:3], start=1):
            title = self._clip_context(str(article.get("title") or "Untitled"), 140)
            source = article.get("source") or article.get("provider") or "unknown source"
            published = article.get("published_at") or "unknown time"
            description = self._clip_context(
                str(article.get("description") or article.get("snippet") or "No article summary returned."),
                220,
            )
            parts.append(f"- {title}\n  Source: {source}; published: {published}\n  Summary: {description}")
        return "\n".join(parts)

    def _format_optional_metric(self, value: Any) -> str:
        number = self._optional_float(value)
        if number is None:
            return "N/A"
        if abs(number) >= 1000:
            return f"{number:,.2f}"
        return f"{number:.4g}"

    def _format_evidence_metric(self, value: Any) -> str:
        number = self._optional_float(value)
        if number is None:
            return "Evidence missing"
        if abs(number) >= 1000:
            return f"{number:,.2f}"
        return f"{number:.4g}"

    def _format_percent(self, value: Any) -> str:
        number = self._optional_float(value)
        if number is None:
            return "Evidence missing"
        return f"{number:.2f}%"

    def _market_direction(self, market_data: dict[str, Any]) -> str:
        trend = str(market_data.get("trend") or "").lower()
        indicators = market_data.get("indicators") or {}
        volatility = self._optional_float(indicators.get("volatility_20"))
        bandwidth = self._optional_float(indicators.get("bollinger_bandwidth"))
        if (volatility is not None and volatility >= 0.04) or (bandwidth is not None and bandwidth >= 0.08):
            return "volatile"
        if "bullish" in trend:
            return "bullish"
        if "bearish" in trend:
            return "bearish"
        return "neutral"

    def _risk_level(self, risk_flags: list[str]) -> str:
        if not risk_flags:
            return "Undetermined"
        if any("No major technical risk flag" in flag for flag in risk_flags):
            return "Moderate"
        if len(risk_flags) >= 2:
            return "Elevated"
        return "Moderate"

    def _defi_fallback_summary(self, defi_context: dict[str, Any] | None, status: str) -> str:
        if status != "available" or not defi_context:
            return status
        chain = defi_context.get("chain_context") or {}
        protocol = defi_context.get("protocol_context") or {}
        parts = []
        if chain:
            parts.append(
                f"{chain.get('chain')} TVL={chain.get('tvl')} 7d_change={chain.get('change_7d')}"
            )
        if protocol:
            parts.append(
                f"{protocol.get('name')} TVL={protocol.get('tvl')} 7d_change={protocol.get('change_7d')}"
            )
        return "; ".join(parts) if parts else "available"
