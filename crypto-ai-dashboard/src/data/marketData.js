export const symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];

export const timeframes = ["1h", "4h", "1d"];

export const sampleQueries = [
  {
    label: "BTC short-term risk",
    engine: "insight",
    symbol: "BTCUSDT",
    question: "Why is BTC moving today and what is the short-term risk?",
  },
  {
    label: "ETH RAG evidence",
    engine: "insight",
    symbol: "ETHUSDT",
    question: "Use RAG retrieved PDF documents and source-grounded context to analyze ETH market risk. Cite the retrieved sources and separate PDF evidence from live market indicators.",
  },
  {
    label: "SOL prediction",
    engine: "prediction",
    symbol: "SOLUSDT",
    question: "Predict SOL trend over the next 3 days using recent market candles.",
  },
];
