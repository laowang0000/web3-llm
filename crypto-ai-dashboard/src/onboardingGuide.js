export const ONBOARDING_STORAGE_KEY = "web3-finance-onboarding-dismissed";

export const onboardingSteps = [
  {
    id: "workspace",
    targetEngine: "insight",
    title: "Choose a workspace",
    eyebrow: "Navigation",
    body: "Use the left navigation on desktop, or the top switcher on mobile, to move between Insight, Prediction and Settings.",
    controls: ["Sidebar buttons", "Mobile engine switch"],
  },
  {
    id: "settings",
    targetEngine: "models",
    title: "Check the backend and model",
    eyebrow: "Runtime setup",
    body: "Open Settings when the backend is offline, when Ollama models need refreshing, or when you want to use a remote provider.",
    controls: ["Check backend", "Refresh models", "Provider dropdown"],
  },
  {
    id: "inputs",
    targetEngine: "insight",
    title: "Tune the market question",
    eyebrow: "Inputs",
    body: "Pick a symbol and timeframe with the dropdowns, then edit the question field or load a sample query from the quick panel.",
    controls: ["Symbol dropdown", "Timeframe dropdown", "Question textarea", "Sample query"],
  },
  {
    id: "prediction",
    targetEngine: "prediction",
    title: "Run a prediction",
    eyebrow: "Prediction flow",
    body: "Prediction uses its own symbol, timeframe, horizon and candle limit. Start with BTC or SOL and a 3-day horizon for a quick demo.",
    controls: ["Horizon dropdown", "Candle limit", "Run Prediction"],
  },
  {
    id: "results",
    targetEngine: "insight",
    title: "Read results and evidence",
    eyebrow: "Output review",
    body: "After running analysis, scan the answer, confidence, indicators and retrieved sources. Source trace cards show where the backend evidence came from.",
    controls: ["Answer panel", "Technical signals", "Retrieved sources"],
  },
];

export function getInitialGuideOpen(storage) {
  try {
    return storage?.getItem(ONBOARDING_STORAGE_KEY) !== "true";
  } catch {
    return false;
  }
}

export function rememberGuideDismissed(storage) {
  try {
    storage?.setItem(ONBOARDING_STORAGE_KEY, "true");
  } catch {
    // Private or restricted browser storage should not block the guide.
  }
}
