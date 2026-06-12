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
    question: "Use the PDF the-eth-value-debate.pdf as retrieved RAG evidence to analyze ETH market risk. Cite the PDF name, page number, retrieved claim, why it matters, and risk implication. Separate PDF evidence from live market indicators.",
  },
  {
    label: "SOL prediction",
    engine: "prediction",
    symbol: "SOLUSDT",
    question: "Predict SOL trend over the next 3 days using recent market candles.",
  },
];
