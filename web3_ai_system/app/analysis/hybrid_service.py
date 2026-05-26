import json
from typing import Any

from app.insight_engine.service import InsightService
from app.llm.ollama_client import OllamaChatClient, OllamaClientError
from app.market_data.service import MarketDataService
from app.news_data.service import LiveNewsService


class HybridAnalysisServiceError(RuntimeError):
    """Raised when hybrid market analysis cannot be completed."""


class HybridAnalysisService:
    def __init__(
        self,
        market_service: MarketDataService | None = None,
        insight_service: InsightService | None = None,
        news_service: LiveNewsService | None = None,
        llm_client: OllamaChatClient | None = None,
    ) -> None:
        self.market_service = market_service or MarketDataService()
        self.insight_service = insight_service or InsightService()
        self.news_service = news_service or LiveNewsService()
        self.llm = llm_client or OllamaChatClient()

    def analyze(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        question: str,
    ) -> tuple[dict[str, Any], list[str]]:
        market_data, market_sources = self.market_service.analyze_basic(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        retrieval_query = self._build_retrieval_query(market_data, question)
        documents = self.insight_service.retrieve(retrieval_query)
        rag_context = self.insight_service.format_context(documents)
        rag_sources = self.insight_service.source_labels(documents)
        retrieved_metadata = self.insight_service.chunk_metadata(documents)

        news_data, news_sources = self.news_service.fetch_relevant_news(symbol=market_data["symbol"], question=question)
        news_context = self.news_service.format_context(news_data)
        news_source_labels = self.news_service.source_labels(news_data)

        prompt_context = self._build_prompt_context(market_data, rag_context, news_context)
        try:
            answer = self.llm.chat(
                message=question,
                system_prompt=self._system_prompt(),
                context=prompt_context,
            )
        except OllamaClientError as exc:
            raise HybridAnalysisServiceError(str(exc)) from exc

        data = {
            "symbol": market_data["symbol"],
            "timeframe": market_data["timeframe"],
            "price": market_data["price"],
            "indicators": market_data["indicators"],
            "trend": market_data["trend"],
            "risk_flags": market_data["risk_flags"],
            "answer": answer,
            "model": self.llm.settings.model,
            "retrieved_context_count": len(documents),
            "retrieved_sources": retrieved_metadata,
            "live_news": news_data,
            "live_news_count": news_data.get("article_count", 0),
            "live_news_warnings": news_data.get("warnings", []),
            "market": market_data.get("market", {}),
            "latest_candle": market_data.get("latest_candle", {}),
        }
        sources = list(dict.fromkeys(market_sources + rag_sources + news_sources + news_source_labels))
        return data, sources

    def _build_retrieval_query(self, market_data: dict[str, Any], question: str) -> str:
        return (
            f"{question}\n"
            f"Symbol: {market_data['symbol']}\n"
            f"Trend: {market_data['trend']}\n"
            f"Risk flags: {'; '.join(market_data['risk_flags'])}"
        )

    def _build_prompt_context(self, market_data: dict[str, Any], rag_context: str, news_context: str) -> str:
        indicators = market_data["indicators"]
        market_payload = {
            "symbol": market_data["symbol"],
            "timeframe": market_data["timeframe"],
            "latest_price": market_data["price"],
            "indicators": {
                "rsi": indicators.get("rsi"),
                "ema_12": indicators.get("ema_12"),
                "ema_20": indicators.get("ema_20"),
                "ema_26": indicators.get("ema_26"),
                "ema_50": indicators.get("ema_50"),
                "macd": indicators.get("macd"),
                "macd_signal": indicators.get("macd_signal"),
                "macd_histogram": indicators.get("macd_histogram"),
                "bollinger_upper": indicators.get("bollinger_upper"),
                "bollinger_middle": indicators.get("bollinger_middle"),
                "bollinger_lower": indicators.get("bollinger_lower"),
                "bollinger_bandwidth": indicators.get("bollinger_bandwidth"),
                "volatility_20": indicators.get("volatility_20"),
            },
            "trend_summary": market_data["trend"],
            "risk_flags": market_data["risk_flags"],
        }

        retrieved_context = rag_context or "No relevant RAG context was retrieved."
        return (
            "Market data and technical indicators:\n"
            f"{json.dumps(market_payload, indent=2)}\n\n"
            "Retrieved RAG context:\n"
            f"{retrieved_context}\n\n"
            "Live news context:\n"
            f"{news_context}"
        )

    def _system_prompt(self) -> str:
        return (
            "You are a cryptocurrency market analysis assistant for an academic FYP MVP. "
            "Use only the provided market data, technical indicators, risk flags, retrieved RAG context, and live news context. "
            "If retrieved context or live news is insufficient, say that clearly. "
            "Separate observed data from interpretation. "
            "Do not provide financial advice, price targets, or unsupported causal claims."
        )
