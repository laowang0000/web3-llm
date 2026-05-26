import os
from typing import Any

from app.market_data.service import normalize_symbol
from app.news_data.gnews_client import GNewsClient, GNewsClientError
from app.news_data.marketaux_client import MarketauxClient, MarketauxClientError


SYMBOL_NEWS_TERMS = {
    "BTCUSDT": ("Bitcoin", "BTC"),
    "ETHUSDT": ("Ethereum", "ETH"),
    "SOLUSDT": ("Solana", "SOL"),
    "MATICUSDT": ("Polygon", "MATIC"),
}


class LiveNewsService:
    """Fetches live article snippets for hybrid RAG-style prompt augmentation."""

    def __init__(
        self,
        marketaux_client: MarketauxClient | None = None,
        gnews_client: GNewsClient | None = None,
        max_articles: int | None = None,
    ) -> None:
        self.marketaux = marketaux_client or MarketauxClient()
        self.gnews = gnews_client or GNewsClient()
        configured_max = int(os.getenv("NEWS_MAX_ARTICLES", "6"))
        self.max_articles = max(1, min(max_articles or configured_max, 12))

    def fetch_relevant_news(self, symbol: str, question: str | None = None) -> tuple[dict[str, Any], list[str]]:
        normalized_symbol = normalize_symbol(symbol)
        marketaux_query = self._marketaux_query(normalized_symbol)
        gnews_query = self._gnews_query(normalized_symbol, question)
        per_provider_limit = max(1, min(self.max_articles, 5))

        articles: list[dict[str, Any]] = []
        warnings: list[str] = []
        sources: list[str] = []

        if self.marketaux.is_configured:
            try:
                articles.extend(self.marketaux.fetch_news(marketaux_query, limit=per_provider_limit))
                sources.append("marketaux:/v1/news/all")
            except MarketauxClientError as exc:
                warnings.append(str(exc))
        else:
            warnings.append("Marketaux is not configured.")

        if self.gnews.is_configured:
            try:
                articles.extend(self.gnews.search(gnews_query, limit=per_provider_limit))
                sources.append("gnews:/api/v4/search")
            except GNewsClientError as exc:
                warnings.append(str(exc))
        else:
            warnings.append("GNews is not configured.")

        deduped_articles = self._deduplicate_articles(articles)[: self.max_articles]
        data = {
            "symbol": normalized_symbol,
            "query": {
                "marketaux": marketaux_query,
                "gnews": gnews_query,
            },
            "articles": deduped_articles,
            "article_count": len(deduped_articles),
            "warnings": warnings,
        }
        return data, sources

    def format_context(self, news_data: dict[str, Any]) -> str:
        articles = news_data.get("articles") or []
        if not articles:
            return "No live news articles were retrieved."

        blocks: list[str] = []
        for index, article in enumerate(articles, start=1):
            title = self._clip(article.get("title"), 180)
            description = self._clip(article.get("description"), 300)
            snippet = self._clip(article.get("snippet"), 360)
            blocks.append(
                f"[Live News {index}] provider={article.get('provider', 'unknown')}; "
                f"source={article.get('source') or 'unknown'}; "
                f"published_at={article.get('published_at') or 'unknown'}; "
                f"url={article.get('url') or 'unknown'}\n"
                f"Title: {title}\n"
                f"Description: {description}\n"
                f"Snippet: {snippet}"
            )
        return "\n\n".join(blocks)

    def source_labels(self, news_data: dict[str, Any]) -> list[str]:
        labels: list[str] = []
        for article in news_data.get("articles") or []:
            provider = article.get("provider", "news")
            source = article.get("source") or article.get("url") or "unknown"
            labels.append(f"{provider}::{source}")
        return labels

    def _marketaux_query(self, symbol: str) -> str:
        terms = SYMBOL_NEWS_TERMS.get(symbol, (symbol.replace("USDT", ""),))
        return "|".join([*terms, "cryptocurrency", "crypto"])

    def _gnews_query(self, symbol: str, question: str | None = None) -> str:
        terms = SYMBOL_NEWS_TERMS.get(symbol, (symbol.replace("USDT", ""),))
        base_query = f"({' OR '.join([*terms, 'cryptocurrency'])})"
        if question and any(word in question.lower() for word in ["why", "moving", "today", "news", "risk"]):
            return f"{base_query} market"
        return base_query

    def _deduplicate_articles(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for article in articles:
            key = str(article.get("url") or article.get("title") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(article)
        return deduped

    def _clip(self, value: Any, max_length: int) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= max_length:
            return text or "N/A"
        return f"{text[: max_length - 3]}..."
