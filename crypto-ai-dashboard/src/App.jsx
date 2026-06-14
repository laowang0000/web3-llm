import { useEffect, useMemo, useState } from "react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import { sampleQueries, symbols, timeframes } from "./data/marketData";
import { Icon } from "./components/icons";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 180000;
const SELECTED_CHAT_MODEL_STORAGE_KEY = "web3-finance-selected-chat-model";
const MODEL_PROVIDER_STORAGE_KEY = "web3-finance-model-provider";
const RECOMMENDED_CHAT_MODEL = "qwen3.5:9b";
const DEFAULT_PROVIDER_SETTINGS = {
  providerType: "local_ollama",
  remoteOllamaBaseUrl: "",
  remoteModelName: "",
  researchApiEndpointUrl: "http://100.124.37.113:5000/v1/research/ask",
  researchApiKey: "",
  openaiBaseUrl: "",
  openaiApiKey: "",
  openaiModelName: "",
};
const MODEL_DESCRIPTIONS = {
  "qwen3.5:9b": "Recommended local model for speed, reliability and acceptable quality.",
  "granite4.1:30b": "Stronger reasoning but slower.",
  "gemma4:31b": "Strong but memory heavy.",
  "qwen3.6:latest": "High-quality option but slow and may timeout.",
};

function App() {
  const [activeEngine, setActiveEngine] = useState("insight");
  const [insightSymbol, setInsightSymbol] = useState("BTCUSDT");
  const [predictionSymbol, setPredictionSymbol] = useState("SOLUSDT");
  const [insightTimeframe, setInsightTimeframe] = useState("1h");
  const [predictionTimeframe, setPredictionTimeframe] = useState("1d");
  const [horizonDays, setHorizonDays] = useState(3);
  const [predictionLimit, setPredictionLimit] = useState(300);
  const [question, setQuestion] = useState(sampleQueries[0].question);
  const [insightResult, setInsightResult] = useState(null);
  const [predictionResult, setPredictionResult] = useState(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [predictionLoading, setPredictionLoading] = useState(false);
  const [insightNotice, setInsightNotice] = useState("");
  const [predictionNotice, setPredictionNotice] = useState("");
  const [systemNotice, setSystemNotice] = useState("");
  const [backendStatus, setBackendStatus] = useState("idle");
  const [runtimeStatus, setRuntimeStatus] = useState({
    status: "idle",
    checkedAt: "",
    components: [],
    error: "",
  });
  const [selectedChatModel, setSelectedChatModel] = useState(() => readStoredChatModel());
  const [providerSettings, setProviderSettings] = useState(() => readStoredProviderSettings());
  const [modelCatalog, setModelCatalog] = useState({
    status: "idle",
    chatModels: [],
    localModels: [],
    excludedModels: [],
    embeddingModel: "nomic-embed-text",
    defaultChatModel: "",
    error: "",
  });
  const [remoteModelCatalog, setRemoteModelCatalog] = useState({
    status: "idle",
    chatModels: [],
    excludedModels: [],
    error: "",
  });
  const [externalTest, setExternalTest] = useState({ status: "idle", message: "" });

  useEffect(() => {
    loadOllamaModels();
  }, []);

  useEffect(() => {
    if (activeEngine === "models") {
      loadRuntimeStatus();
    }
  }, [activeEngine]);

  useEffect(() => {
    if (selectedChatModel) {
      window.localStorage.setItem(SELECTED_CHAT_MODEL_STORAGE_KEY, selectedChatModel);
    }
  }, [selectedChatModel]);

  useEffect(() => {
    writeStoredProviderSettings(providerSettings);
  }, [providerSettings]);

  async function loadOllamaModels() {
    setModelCatalog((current) => ({ ...current, status: "loading", error: "" }));
    try {
      const payload = await requestBackend("/models/ollama");
      const data = payload.data || {};
      const chatModels = Array.isArray(data.chat_models) ? data.chat_models : [];
      const nextSelected = chooseChatModel(selectedChatModel, chatModels, data.default_chat_model);
      setModelCatalog({
        status: "ready",
        chatModels,
        localModels: Array.isArray(data.local_models) ? data.local_models : [],
        excludedModels: Array.isArray(data.excluded_models) ? data.excluded_models : [],
        embeddingModel: data.embedding_model || "nomic-embed-text",
        defaultChatModel: data.default_chat_model || "",
        error: "",
      });
      if (nextSelected && nextSelected !== selectedChatModel) {
        setSelectedChatModel(nextSelected);
      }
      setBackendStatus("online");
    } catch (error) {
      setModelCatalog((current) => ({
        ...current,
        status: "error",
        chatModels: [],
        error: "Ollama is not running or local models cannot be detected.",
      }));
      setBackendStatus(error.name === "TypeError" || error.name === "AbortError" ? "offline" : "online");
    }
  }

  async function testExternalProvider() {
    const providerConfig = buildProviderConfig(providerSettings, selectedChatModel);
    setExternalTest({ status: "loading", message: "" });
    if (!providerConfig) {
      setExternalTest({ status: "ready", message: "Local Ollama is already the default provider." });
      return;
    }
    try {
      const payload = await requestBackend("/models/test-connection", {
        method: "POST",
        body: JSON.stringify({ provider_config: providerConfig }),
      });
      const data = payload.data || {};
      const chatModels = Array.isArray(data.chat_models) ? data.chat_models : Array.isArray(data.available_models) ? data.available_models : [];
      if (providerConfig.provider_type === "remote_ollama") {
        const nextRemoteModel = chooseChatModel(providerSettings.remoteModelName, chatModels, data.default_chat_model);
        setRemoteModelCatalog({
          status: "ready",
          chatModels,
          excludedModels: Array.isArray(data.excluded_models) ? data.excluded_models : [],
          error: "",
        });
        if (nextRemoteModel) {
          setProviderSettings((current) => ({ ...current, remoteModelName: nextRemoteModel }));
        }
      }
      setExternalTest({ status: "ready", message: "Connection test succeeded." });
      setBackendStatus("online");
    } catch (error) {
      const message = formatBackendError(error);
      if (providerConfig.provider_type === "remote_ollama") {
        setRemoteModelCatalog((current) => ({ ...current, status: "error", error: message }));
      }
      setExternalTest({ status: "error", message });
      setBackendStatus(error.name === "TypeError" || error.name === "AbortError" ? "offline" : "online");
    }
  }

  async function checkBackend() {
    setBackendStatus("checking");
    setSystemNotice("");
    try {
      await requestBackend("/health");
      setBackendStatus("online");
      await loadRuntimeStatus();
    } catch (error) {
      setBackendStatus("offline");
      setRuntimeStatus({
        status: "error",
        checkedAt: new Date().toLocaleTimeString(),
        components: [],
        error: formatBackendError(error),
      });
      setSystemNotice(formatBackendError(error));
    }
  }

  async function loadRuntimeStatus() {
    setRuntimeStatus((current) => ({ ...current, status: current.status === "idle" ? "loading" : current.status, error: "" }));
    try {
      const payload = await requestBackend("/runtime/status");
      const data = payload.data || {};
      setRuntimeStatus({
        status: data.status || "ok",
        checkedAt: new Date().toLocaleTimeString(),
        components: Array.isArray(data.components) ? data.components : [],
        error: "",
      });
      setBackendStatus("online");
    } catch (error) {
      setRuntimeStatus({
        status: "error",
        checkedAt: new Date().toLocaleTimeString(),
        components: [],
        error: formatBackendError(error),
      });
      setBackendStatus(error.name === "TypeError" || error.name === "AbortError" ? "offline" : "online");
    }
  }

  async function runInsight() {
    setActiveEngine("insight");
    setInsightLoading(true);
    setInsightNotice("");
    setInsightResult(null);
    try {
      const payload = await requestBackend("/analyze", {
        method: "POST",
        body: JSON.stringify({
          symbol: insightSymbol,
          timeframe: insightTimeframe,
          limit: 120,
          question,
          selected_model: providerSettings.providerType === "local_ollama" ? selectedChatModel || undefined : undefined,
          provider_config: buildProviderConfig(providerSettings, selectedChatModel),
        }),
      });
      setInsightResult({ ...payload.data, sources: payload.sources || [] });
      setBackendStatus("online");
    } catch (error) {
      setInsightNotice(`${formatBackendError(error)} No frontend fallback result was generated.`);
      setBackendStatus(error.name === "TypeError" || error.name === "AbortError" ? "offline" : "online");
    } finally {
      setInsightLoading(false);
    }
  }

  async function runPrediction() {
    setActiveEngine("prediction");
    setPredictionLoading(true);
    setPredictionNotice("");
    setPredictionResult(null);
    try {
      const payload = await requestBackend("/predict", {
        method: "POST",
        body: JSON.stringify({
          symbol: predictionSymbol,
          timeframe: predictionTimeframe,
          horizon_candles: Number(horizonDays),
          limit: Number(predictionLimit),
        }),
      });
      setPredictionResult({ ...payload.data, sources: payload.sources || [] });
      setBackendStatus("online");
    } catch (error) {
      setPredictionNotice(`${formatBackendError(error)} No frontend fallback result was generated.`);
      setBackendStatus(error.name === "TypeError" || error.name === "AbortError" ? "offline" : "online");
    } finally {
      setPredictionLoading(false);
    }
  }

  const activeTitle = activeEngine === "insight" ? "Insight Engine" : activeEngine === "prediction" ? "Prediction Engine" : "Settings";
  const activeNotice = activeEngine === "insight" ? insightNotice : activeEngine === "prediction" ? predictionNotice : systemNotice;
  const activeSymbol = activeEngine === "prediction" ? predictionSymbol : insightSymbol;
  const activeSetSymbol = activeEngine === "prediction" ? setPredictionSymbol : setInsightSymbol;
  const activeTimeframe = activeEngine === "prediction" ? predictionTimeframe : insightTimeframe;
  const activeSetTimeframe = activeEngine === "prediction" ? setPredictionTimeframe : setInsightTimeframe;

  return (
    <div className="min-h-screen bg-surface-950 text-ink-50">
      <div className="pointer-events-none fixed inset-0 z-0 opacity-[0.03] [background-image:radial-gradient(circle_at_1px_1px,#f7f1e3_1px,transparent_0)] [background-size:24px_24px]" />
      <div className="relative z-10 flex min-h-screen">
        <Sidebar activeEngine={activeEngine} onEngineChange={setActiveEngine} />

        <main className="min-w-0 flex-1">
          <Header backendStatus={backendStatus} onCheckBackend={checkBackend} />

          <section className="mx-auto flex w-full max-w-[1180px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8">
            <MobileEngineSwitch activeEngine={activeEngine} onEngineChange={setActiveEngine} />

            {activeEngine === "models" ? (
              <ModelSettingsPage
                modelCatalog={modelCatalog}
                remoteModelCatalog={remoteModelCatalog}
                providerSettings={providerSettings}
                setProviderSettings={setProviderSettings}
                externalTest={externalTest}
                selectedChatModel={selectedChatModel}
                setSelectedChatModel={setSelectedChatModel}
                onRefresh={loadOllamaModels}
                onTestExternalProvider={testExternalProvider}
                backendStatus={backendStatus}
                runtimeStatus={runtimeStatus}
                onRefreshRuntimeStatus={loadRuntimeStatus}
              />
            ) : (
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
                <WorkspaceCard
                  activeEngine={activeEngine}
                  activeTitle={activeTitle}
                  symbol={activeSymbol}
                  setSymbol={activeSetSymbol}
                  timeframe={activeTimeframe}
                  setTimeframe={activeSetTimeframe}
                  horizonDays={horizonDays}
                  setHorizonDays={setHorizonDays}
                  predictionLimit={predictionLimit}
                  setPredictionLimit={setPredictionLimit}
                  question={question}
                  setQuestion={setQuestion}
                  loading={activeEngine === "insight" ? insightLoading : predictionLoading}
                  onRunInsight={runInsight}
                  onRunPrediction={runPrediction}
                  selectedChatModel={selectedChatModel}
                  providerSettings={providerSettings}
                  onOpenModelSettings={() => setActiveEngine("models")}
                />

                <QuickPanel
                  activeEngine={activeEngine}
                  setActiveEngine={setActiveEngine}
                  setInsightSymbol={setInsightSymbol}
                  setPredictionSymbol={setPredictionSymbol}
                  setQuestion={setQuestion}
                  selectedChatModel={selectedChatModel}
                  providerSettings={providerSettings}
                />
              </div>
            )}

            {activeNotice && (
              <div className="rounded-2xl border border-accent-gold/22 bg-accent-gold/8 px-4 py-3 text-sm leading-6 text-accent-champagne">
                {activeNotice}
              </div>
            )}

            {activeEngine === "insight" ? (
              <InsightResults result={insightResult} loading={insightLoading} />
            ) : activeEngine === "prediction" ? (
              <PredictionResults result={predictionResult} loading={predictionLoading} />
            ) : null}
          </section>
        </main>
      </div>
    </div>
  );
}

function MobileEngineSwitch({ activeEngine, onEngineChange }) {
  return (
    <div className="grid grid-cols-3 gap-2 rounded-full border border-line-soft bg-surface-950 p-1.5 lg:hidden">
      {[
        ["insight", "Insight"],
        ["prediction", "Predict"],
        ["models", "Settings"],
      ].map(([id, label]) => (
        <button
          key={id}
          onClick={() => onEngineChange(id)}
          className={`h-11 rounded-full text-sm font-semibold transition-all duration-700 ease-premium ${
            activeEngine === id ? "bg-accent-gold text-surface-950 shadow-glow" : "text-ink-300"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function WorkspaceCard(props) {
  const isInsight = props.activeEngine === "insight";
  const activeModelLabel = describeActiveProviderModel(props.providerSettings, props.selectedChatModel);

  return (
    <section className="gold-shell animate-in rounded-[1.8rem]">
      <div className="gold-core rounded-[1.45rem] p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-gold/85">{props.activeTitle}</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink-50">
              {isInsight ? "Ask a market risk question" : "Run backend trend prediction"}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-300">
              {isInsight
                ? "This presentation layer sends the question to FastAPI /analyze and renders the returned JSON answer, indicators and source trace."
                : "This presentation layer sends OHLCV settings to FastAPI /predict and renders the returned trend probability and model evidence."}
            </p>
          </div>
          <span className="rounded-full border border-accent-green/22 bg-accent-green/10 px-3 py-1 text-xs font-semibold text-accent-green">
            Backend JSON only
          </span>
        </div>

        <div className={`mt-5 grid gap-4 ${isInsight ? "lg:grid-cols-3" : "sm:grid-cols-2"}`}>
          <SelectGroup label="Symbol" value={props.symbol} options={symbols} onChange={props.setSymbol} />
          <SelectGroup label="Timeframe" value={props.timeframe} options={timeframes} onChange={props.setTimeframe} />
          {isInsight ? (
            <ReadOnlyField label="Candle limit" value="120" />
          ) : (
            <>
              <SelectGroup label="Horizon" value={String(props.horizonDays)} options={["1", "3", "5", "7"]} onChange={(value) => props.setHorizonDays(Number(value))} />
              <SelectGroup label="Candle limit" value={String(props.predictionLimit)} options={["240", "300", "365"]} onChange={(value) => props.setPredictionLimit(Number(value))} />
            </>
          )}
        </div>

        {isInsight && (
          <label className="mt-5 block">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">Question</span>
            <textarea
              value={props.question}
              onChange={(event) => props.setQuestion(event.target.value)}
              className="mt-2 min-h-[126px] w-full resize-none rounded-[1.25rem] border border-line-soft bg-surface-950 p-4 text-sm leading-7 text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
              placeholder="Ask a crypto market question..."
            />
          </label>
        )}

        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
          <button
            data-testid={isInsight ? "run-insight" : "run-prediction"}
            onClick={isInsight ? props.onRunInsight : props.onRunPrediction}
            disabled={props.loading || (isInsight && !props.question.trim())}
            className="group flex h-14 items-center justify-between rounded-full bg-accent-gold px-5 font-semibold text-surface-950 shadow-glow transition-all duration-700 ease-premium hover:bg-accent-champagne active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-[260px]"
          >
            {props.loading ? "Waiting for backend..." : isInsight ? "Run Insight Analysis" : "Run Prediction"}
            <span className="grid h-9 w-9 place-items-center rounded-full bg-surface-950/12 transition-transform duration-700 ease-premium group-hover:translate-x-1">
              <Icon name={isInsight ? "brain" : "trend"} className="h-4 w-4" />
            </span>
          </button>
          <button
            onClick={props.onOpenModelSettings}
            className="ghost-button h-12 text-sm"
          >
            Model settings
          </button>
          <button
            onClick={() => {
              props.setQuestion(sampleQueries[0].question);
              props.setSymbol("BTCUSDT");
            }}
            className="ghost-button h-12 text-sm"
          >
            Reset input
          </button>
        </div>
        {isInsight && (
          <p className="mt-3 text-sm leading-6 text-ink-400">
            Active model provider: <span className="number-font text-accent-champagne">{activeModelLabel}</span>
          </p>
        )}
        {props.loading && (
          <p className="mt-3 text-sm leading-6 text-ink-400">
            Running live backend analysis. Market fallback, RAG retrieval and Ollama generation can take around 20-40 seconds on a local machine.
          </p>
        )}
      </div>
    </section>
  );
}

function QuickPanel({
  setActiveEngine,
  setInsightSymbol,
  setPredictionSymbol,
  setQuestion,
  selectedChatModel,
  providerSettings,
}) {
  const [selectedExample, setSelectedExample] = useState("");
  const activeModelLabel = describeActiveProviderModel(providerSettings, selectedChatModel);
  const selectedItem = sampleQueries.find((item) => item.label === selectedExample);

  function applyExample(label) {
    const item = sampleQueries.find((sample) => sample.label === label);
    setSelectedExample(label);
    if (!item) return;
    setActiveEngine(item.engine);
    if (item.engine === "prediction") {
      setPredictionSymbol(item.symbol);
    } else {
      setInsightSymbol(item.symbol);
      setQuestion(item.question);
    }
  }

  return (
    <aside className="space-y-4">
      <div className="gold-shell rounded-[1.8rem]">
        <div className="gold-core rounded-[1.45rem] p-5">
          <h3 className="text-lg font-semibold text-ink-50">Quick examples</h3>
          <p className="mt-1 text-sm text-ink-300">Pick one preset to fill the workspace for demo.</p>
          <label className="mt-4 block">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">Demo preset</span>
            <select
              data-testid="quick-example-select"
              value={selectedExample}
              onChange={(event) => applyExample(event.target.value)}
              className="mt-2 min-h-[52px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
            >
              <option value="">Select BTC, ETH, or SOL demo</option>
              {sampleQueries.map((item) => (
                <option key={item.label} value={item.label}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <div className="mt-4 rounded-2xl border border-line-cool bg-white/[0.045] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-gold/80">Selected flow</p>
            <p className="mt-2 text-sm font-semibold text-ink-50">{selectedItem ? selectedItem.label : "No preset selected"}</p>
            <p className="mt-2 text-sm leading-6 text-ink-200">
              {selectedItem ? selectedItem.question : "Use the dropdown to load one of the three demo-ready examples."}
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-[1.45rem] border border-line-soft bg-surface-900/90 p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-gold/85">Runtime context</p>
        <div className="mt-4 grid gap-3">
          <MetricRow label="Active model" value={activeModelLabel} />
          <MetricRow label="Insight route" value="POST /analyze" />
          <MetricRow label="Prediction route" value="POST /predict" />
        </div>
      </div>
    </aside>
  );
}

function ConnectionDashboard({ backendStatus, runtimeStatus, onRefresh }) {
  const hasRuntimeResponse = Array.isArray(runtimeStatus.components) && runtimeStatus.components.length > 0;
  const backendOk = backendStatus === "online" || hasRuntimeResponse;
  const frontendConnection = {
    name: "React UI -> FastAPI",
    status: backendOk ? "ok" : backendStatus === "checking" || runtimeStatus.status === "loading" ? "loading" : "error",
    message: backendOk
      ? "React can reach the FastAPI JSON API."
      : "React cannot confirm the FastAPI JSON API right now.",
  };
  const components = [frontendConnection, ...(Array.isArray(runtimeStatus.components) ? runtimeStatus.components : [])];
  const summary = runtimeStatus.status === "ok" && backendOk ? "All required links ready" : runtimeStatus.status === "warning" ? "Some optional context unavailable" : runtimeStatus.status === "loading" ? "Checking connections" : "Attention needed";

  return (
    <div className="gold-shell rounded-[1.8rem]">
      <div className="gold-core rounded-[1.45rem] p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-gold/85">Connection Dashboard</p>
            <h3 className="mt-2 text-lg font-semibold text-ink-50">{summary}</h3>
            <p className="mt-1 text-xs leading-5 text-ink-400">
              Checks React, FastAPI, Ollama, RAG and optional context providers.
            </p>
          </div>
          <button onClick={onRefresh} className="ghost-button h-10 px-3 text-xs">
            Refresh
          </button>
        </div>

        {runtimeStatus.error && (
          <p className="mt-4 rounded-2xl border border-accent-red/22 bg-accent-red/8 p-3 text-xs leading-5 text-accent-red">
            {runtimeStatus.error}
          </p>
        )}

        <div className="mt-4 space-y-2">
          {components.map((component) => (
            <ConnectionRow key={component.name} component={component} />
          ))}
        </div>

        <p className="mt-3 text-xs leading-5 text-ink-500">
          Last checked: {runtimeStatus.checkedAt || "not checked yet"}
        </p>
      </div>
    </div>
  );
}

function ConnectionRow({ component }) {
  const statusValue = component?.status || "warning";
  const message = component?.message || "No status message returned.";
  return (
    <div className="rounded-2xl border border-line-cool bg-white/[0.025] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink-50">{component?.name || "Unknown component"}</p>
          <p className="mt-1 text-xs leading-5 text-ink-400">{message}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusBadgeClass(statusValue)}`}>
          {statusLabel(statusValue)}
        </span>
      </div>
    </div>
  );
}

function statusLabel(statusValue) {
  if (statusValue === "ok") return "OK";
  if (statusValue === "error") return "Issue";
  if (statusValue === "loading") return "Checking";
  return "Check";
}

function statusBadgeClass(statusValue) {
  if (statusValue === "ok") return "border-accent-green/22 bg-accent-green/10 text-accent-green";
  if (statusValue === "error") return "border-accent-red/22 bg-accent-red/10 text-accent-red";
  if (statusValue === "loading") return "border-accent-gold/22 bg-accent-gold/10 text-accent-gold";
  return "border-line-soft bg-white/[0.025] text-ink-400";
}

function ModelSettingsPage({
  modelCatalog,
  remoteModelCatalog,
  providerSettings,
  setProviderSettings,
  externalTest,
  selectedChatModel,
  setSelectedChatModel,
  onRefresh,
  onTestExternalProvider,
  backendStatus,
  runtimeStatus,
  onRefreshRuntimeStatus,
}) {
  const chatModels = modelCatalog.chatModels;
  const selectedDescription = MODEL_DESCRIPTIONS[selectedChatModel] || "Local Ollama chat model detected from the backend.";
  const isLoading = modelCatalog.status === "loading";
  const hasModels = chatModels.length > 0;
  const providerType = providerSettings.providerType;
  const remoteHasModels = remoteModelCatalog.chatModels.length > 0;
  const displayedModels = providerType === "remote_ollama" ? remoteModelCatalog.chatModels : providerType === "research_api" ? [] : chatModels;
  const hasDisplayedModels = displayedModels.length > 0;

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="gold-shell animate-in rounded-[1.8rem]">
        <div className="gold-core rounded-[1.45rem] p-5 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-gold/85">Runtime Control</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink-50">Settings</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-300">
                External model provider allows the system to use a remote GPU server, hosted API model, or OpenAI-compatible local server.
              </p>
            </div>
            {providerType === "local_ollama" && (
              <button onClick={onRefresh} disabled={isLoading} className="ghost-button h-12 text-sm disabled:cursor-not-allowed disabled:opacity-50">
                {isLoading ? "Detecting..." : "Refresh models"}
              </button>
            )}
          </div>

          <label className="mt-6 block">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">External Model Provider</span>
            <select
              value={providerType}
              onChange={(event) => setProviderSettings((current) => ({ ...current, providerType: event.target.value }))}
              className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
            >
              <option value="local_ollama">Local Ollama</option>
              <option value="remote_ollama">Remote Ollama</option>
              <option value="research_api">Remote Research API</option>
              <option value="openai_compatible">OpenAI-compatible API</option>
            </select>
          </label>

          {providerType === "local_ollama" && modelCatalog.status === "error" && (
            <div className="mt-5 rounded-2xl border border-accent-red/22 bg-accent-red/10 p-4 text-sm leading-6 text-ink-200">
              {modelCatalog.error || "Ollama is not running or local models cannot be detected."}
            </div>
          )}

          {providerType === "local_ollama" && (
            <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">Local detected chat model</span>
                <select
                  value={hasModels ? selectedChatModel : ""}
                  onChange={(event) => setSelectedChatModel(event.target.value)}
                  disabled={!hasModels || isLoading}
                  className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {!hasModels && <option value="">No local chat models detected</option>}
                  {chatModels.map((modelName) => (
                    <option key={modelName} value={modelName}>
                      {modelName}
                    </option>
                  ))}
                </select>
                <p className="mt-3 text-sm leading-6 text-ink-300">{selectedChatModel ? selectedDescription : "Run Ollama locally, then refresh model detection."}</p>
              </label>

              <div className="rounded-[1.25rem] border border-line-cool bg-white/[0.025] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-500">Current selected chat model</p>
                <p className="number-font mt-2 text-lg font-semibold text-ink-50">{selectedChatModel || "N/A"}</p>
                {selectedChatModel === RECOMMENDED_CHAT_MODEL && (
                  <p className="mt-2 text-xs font-semibold text-accent-green">Recommended for local runtime stability</p>
                )}
              </div>
            </div>
          )}

          {providerType === "remote_ollama" && (
            <div className="mt-6 space-y-5">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">Remote Ollama Base URL</span>
                <input
                  value={providerSettings.remoteOllamaBaseUrl}
                  onChange={(event) => setProviderSettings((current) => ({ ...current, remoteOllamaBaseUrl: event.target.value }))}
                  className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
                  placeholder="http://192.168.1.10:11434"
                />
              </label>
              <button onClick={onTestExternalProvider} disabled={!providerSettings.remoteOllamaBaseUrl || externalTest.status === "loading"} className="ghost-button h-12 text-sm disabled:cursor-not-allowed disabled:opacity-50">
                {externalTest.status === "loading" ? "Testing..." : "Test Connection"}
              </button>
              {remoteModelCatalog.status === "error" && (
                <div className="rounded-2xl border border-accent-red/22 bg-accent-red/10 p-4 text-sm leading-6 text-ink-200">
                  {remoteModelCatalog.error || "Remote Ollama connection failed."}
                </div>
              )}
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">Remote Ollama model</span>
                <select
                  value={remoteHasModels ? providerSettings.remoteModelName : ""}
                  onChange={(event) => setProviderSettings((current) => ({ ...current, remoteModelName: event.target.value }))}
                  disabled={!remoteHasModels}
                  className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {!remoteHasModels && <option value="">Test connection to detect remote models</option>}
                  {remoteModelCatalog.chatModels.map((modelName) => (
                    <option key={modelName} value={modelName}>
                      {modelName}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {providerType === "research_api" && (
            <div className="mt-6 grid gap-5">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">Research API Endpoint</span>
                <input
                  value={providerSettings.researchApiEndpointUrl}
                  onChange={(event) => setProviderSettings((current) => ({ ...current, researchApiEndpointUrl: event.target.value }))}
                  className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
                  placeholder="http://100.124.37.113:5000/v1/research/ask"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">Authentication Key</span>
                <input
                  type="password"
                  value={providerSettings.researchApiKey}
                  onChange={(event) => setProviderSettings((current) => ({ ...current, researchApiKey: event.target.value }))}
                  className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
                  placeholder="Not stored in localStorage"
                />
                <p className="mt-2 text-xs leading-5 text-accent-champagne">Sent as Authorization: Bearer key. It is kept in this browser session only.</p>
              </label>
              <button
                onClick={onTestExternalProvider}
                disabled={!providerSettings.researchApiEndpointUrl || !providerSettings.researchApiKey || externalTest.status === "loading"}
                className="ghost-button h-12 w-fit text-sm disabled:cursor-not-allowed disabled:opacity-50"
              >
                {externalTest.status === "loading" ? "Testing..." : "Test Connection"}
              </button>
            </div>
          )}

          {providerType === "openai_compatible" && (
            <div className="mt-6 grid gap-5">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">API Base URL</span>
                <input
                  value={providerSettings.openaiBaseUrl}
                  onChange={(event) => setProviderSettings((current) => ({ ...current, openaiBaseUrl: event.target.value }))}
                  className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
                  placeholder="https://api.openai.com/v1"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">API Key</span>
                <input
                  type="password"
                  value={providerSettings.openaiApiKey}
                  onChange={(event) => setProviderSettings((current) => ({ ...current, openaiApiKey: event.target.value }))}
                  className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
                  placeholder="Not stored in localStorage"
                />
                <p className="mt-2 text-xs leading-5 text-accent-champagne">API key is kept in this browser session only and is not stored in localStorage.</p>
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">Model Name</span>
                <input
                  value={providerSettings.openaiModelName}
                  onChange={(event) => setProviderSettings((current) => ({ ...current, openaiModelName: event.target.value }))}
                  className="mt-2 min-h-[56px] w-full rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50 outline-none subtle-ring transition-all duration-700 ease-premium focus:border-accent-gold/35"
                  placeholder="gpt-4o-mini, deepseek-chat, llama-3.1-70b, ..."
                />
              </label>
              <button
                onClick={onTestExternalProvider}
                disabled={!providerSettings.openaiBaseUrl || !providerSettings.openaiApiKey || !providerSettings.openaiModelName || externalTest.status === "loading"}
                className="ghost-button h-12 w-fit text-sm disabled:cursor-not-allowed disabled:opacity-50"
              >
                {externalTest.status === "loading" ? "Testing..." : "Test Connection"}
              </button>
            </div>
          )}

          {providerType !== "local_ollama" && externalTest.message && (
            <div className={`mt-5 rounded-2xl border p-4 text-sm leading-6 ${externalTest.status === "error" ? "border-accent-red/22 bg-accent-red/10 text-ink-200" : "border-accent-green/22 bg-accent-green/10 text-accent-green"}`}>
              {externalTest.message}
            </div>
          )}

          <div className="mt-6 rounded-[1.25rem] border border-accent-gold/22 bg-accent-gold/8 p-4">
            <p className="text-sm font-semibold text-accent-champagne">Embedding model is fixed for RAG consistency</p>
            <p className="number-font mt-2 text-lg font-semibold text-ink-50">{modelCatalog.embeddingModel || "nomic-embed-text"}</p>
            <p className="mt-2 text-sm leading-6 text-ink-300">
              This model is not selectable here because changing it can make the existing Chroma vector index inconsistent.
            </p>
          </div>
        </div>
      </div>

      <aside className="space-y-5">
        <ConnectionDashboard
          backendStatus={backendStatus}
          runtimeStatus={runtimeStatus}
          onRefresh={onRefreshRuntimeStatus}
        />

        <div className="gold-shell rounded-[1.8rem]">
          <div className="gold-core rounded-[1.45rem] p-5">
            <h3 className="text-lg font-semibold text-ink-50">{providerType === "remote_ollama" ? "Remote chat models" : providerType === "research_api" ? "Research API model" : "Available local chat models"}</h3>
            {hasDisplayedModels ? (
              <div className="mt-4 space-y-3">
                {displayedModels.map((modelName) => (
                  <div key={modelName} className="rounded-2xl border border-line-cool bg-white/[0.025] p-4">
                    <p className="number-font text-sm font-semibold text-ink-50">{modelName}</p>
                    <p className="mt-2 text-xs leading-5 text-ink-400">{MODEL_DESCRIPTIONS[modelName] || "Detected Ollama chat model."}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-ink-400">
                {providerType === "remote_ollama"
                  ? "Test the remote connection to list models."
                  : providerType === "research_api"
                    ? "This provider exposes one remote research chat endpoint. Use Test Connection to verify it over Tailscale."
                    : "Ollama is not running or local models cannot be detected."}
              </p>
            )}
          </div>
        </div>

        <div className="rounded-[1.45rem] border border-line-soft bg-surface-900/90 p-5">
          <h3 className="text-lg font-semibold text-ink-50">Filtered out</h3>
          {modelCatalog.excludedModels.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {modelCatalog.excludedModels.map((modelName) => (
                <span key={modelName} className="rounded-full border border-line-soft bg-white/[0.025] px-3 py-1.5 text-xs font-semibold text-ink-400">
                  {modelName}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-ink-400">No embedding or special-purpose models were returned by Ollama.</p>
          )}
        </div>

        <div className="rounded-[1.45rem] border border-line-soft bg-surface-900/90 p-5">
          <h3 className="text-lg font-semibold text-ink-50">Custom endpoint placeholder</h3>
          <p className="mt-3 text-sm leading-6 text-ink-400">
            Custom endpoints are reserved for future providers that do not match Ollama, OpenAI-compatible, or the MMU Research API shape.
          </p>
        </div>
      </aside>
    </section>
  );
}

function InsightResults({ result, loading }) {
  const indicators = useMemo(() => normalizeIndicators(result), [result]);
  const riskFlags = asArray(result?.risk_flags || result?.riskFlags);

  if (loading) return <LoadingPanel title="Waiting for FastAPI /analyze..." />;
  if (!result) return <EmptyPanel title="No backend insight yet" body="Choose a symbol, write a question, then run Insight Analysis." icon="brain" />;
  if (result.guardrail_triggered) return <SymbolGuardrailWarning result={result} />;

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="gold-shell animate-in rounded-[1.8rem]">
        <div className="gold-core rounded-[1.45rem] p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-gold/85">FastAPI /analyze</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink-50">{result.symbol || "Market"} Insight</h2>
            </div>
            <ModeBadge label="Live backend" />
          </div>
          <p className="mt-5 whitespace-pre-line rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5 text-sm leading-8 text-ink-200">
            {result.answer || "The backend response did not include an answer field."}
          </p>
          <SourceTrace result={result} embedded />
          <div className="mt-5">
            <h3 className="text-sm font-semibold text-ink-50">Risk flags</h3>
            {riskFlags.length > 0 ? (
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                {riskFlags.map((flag) => (
                  <div key={flag} className="rounded-2xl border border-accent-red/18 bg-accent-red/8 p-4 text-sm leading-6 text-ink-300">
                    {flag}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 rounded-2xl border border-line-soft bg-white/[0.025] p-4 text-sm text-ink-400">No risk flags returned by backend.</p>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-5">
        <MarketSummary result={result} />
        <AnalysisRoutePanel result={result} />
        <IndicatorGrid indicators={indicators} />
      </div>
    </section>
  );
}

function SymbolGuardrailWarning({ result }) {
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="gold-shell animate-in rounded-[1.8rem]">
        <div className="gold-core rounded-[1.45rem] p-5 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-gold/85">Symbol guardrail</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink-50">Analysis stopped before LLM generation</h2>
            </div>
            <span className="rounded-full border border-accent-red/22 bg-accent-red/10 px-3 py-1 text-xs font-semibold text-accent-red">
              Guardrail triggered
            </span>
          </div>

          <div className="mt-6 rounded-[1.25rem] border border-accent-red/22 bg-accent-red/8 p-5">
            <p className="text-sm font-semibold text-ink-50">{result.message || "The selected symbol does not match the question context."}</p>
            {result.suggested_action && (
              <p className="mt-3 text-sm leading-6 text-ink-300">{result.suggested_action}</p>
            )}
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <MetricRow label="Selected symbol" value={result.selected_symbol || "N/A"} />
            <MetricRow label="Question symbol" value={result.question_symbol || "N/A"} />
          </div>
        </div>
      </div>

      <aside className="space-y-5">
        <AnalysisRoutePanel result={result} />
        <div className="rounded-[1.45rem] border border-line-soft bg-surface-900/90 p-5">
          <h3 className="text-lg font-semibold text-ink-50">Context protection</h3>
          <p className="mt-3 text-sm leading-6 text-ink-300">
            No Ollama call, market-data fetch, RAG retrieval, news lookup, or DeFiLlama context was used for this guarded request.
          </p>
        </div>
      </aside>
    </section>
  );
}

function PredictionResults({ result, loading }) {
  if (loading) return <LoadingPanel title="Waiting for FastAPI /predict..." />;
  if (!result) return <EmptyPanel title="No backend prediction yet" body="Choose symbol, timeframe and horizon, then run Prediction." icon="gauge" />;

  const up = toNullableNumber(result.probability_up ?? result.probabilityUp);
  const down = toNullableNumber(result.probability_down ?? result.probabilityDown);
  const metrics = isPlainObject(result.metrics) ? result.metrics : {};
  const baseline = isPlainObject(metrics.baseline) ? metrics.baseline : {};
  const confusion = isPlainObject(metrics.confusion_matrix) ? metrics.confusion_matrix : {};
  const support = isPlainObject(metrics.support) ? metrics.support : {};
  const modelSelection = isPlainObject(result.model_selection) ? result.model_selection : isPlainObject(metrics.model_selection) ? metrics.model_selection : {};
  const modelCandidates = asArray(result.model_candidates || modelSelection.candidate_models);
  const evaluation = isPlainObject(result.evaluation) ? result.evaluation : {};
  const features = asArray(result.features);
  const notes = asArray(result.notes);
  const hasMetrics = Object.keys(metrics).length > 0;
  const targetAchieved = Boolean(result.target_85_achieved ?? metrics.target_85_achieved);

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="gold-shell animate-in rounded-[1.8rem]">
        <div className="gold-core rounded-[1.45rem] p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-gold/85">FastAPI /predict</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink-50">{result.symbol || "Market"} Trend: {result.predicted_trend || result.trend || "N/A"}</h2>
              <p className="mt-2 text-sm leading-6 text-ink-300">Horizon: {result.horizon_label || `future ${result.horizon_candles || result.horizon_days || "N/A"} candles`}</p>
            </div>
            <ModeBadge label="Live backend" />
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <ProbabilityCard label="Probability UP" value={up} tone="up" />
            <ProbabilityCard label="Probability DOWN" value={down} tone="down" />
          </div>

          <div className="mt-6 rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5">
            <p className="text-sm font-semibold text-ink-50">Evaluation metrics</p>
            {hasMetrics ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-4">
                <MetricCard label="Accuracy" value={formatPercent(metrics.accuracy)} />
                <MetricCard label="Precision" value={formatPercent(metrics.precision)} />
                <MetricCard label="Recall" value={formatPercent(metrics.recall)} />
                <MetricCard label="F1-score" value={formatPercent(metrics.f1)} />
                <MetricCard label="85% target" value={targetAchieved ? "true" : "false"} />
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink-400">No metrics object returned by backend.</p>
            )}
            {result.sample_warning && (
              <p className="mt-3 rounded-2xl border border-accent-red/18 bg-accent-red/8 p-4 text-sm leading-6 text-ink-300">{result.sample_warning}</p>
            )}
          </div>

          {hasMetrics && (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <BaselinePanel metrics={metrics} baseline={baseline} />
              <ConfusionMatrixPanel confusion={confusion} support={support} />
            </div>
          )}

          <ModelComparisonPanel candidates={modelCandidates} selectedModel={result.model_name} />

          <div className="mt-6 rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5">
            <p className="text-sm font-semibold text-ink-50">Interpretation</p>
            <p className="mt-3 text-sm leading-6 text-ink-300">
              {evaluation.summary || "The backend did not return a prediction interpretation summary."}
            </p>
            <p className="mt-3 text-xs leading-5 text-ink-400">
              {evaluation.reliability || "Reliability depends on chronological test-window size and baseline comparison."}
            </p>
            {result.disclaimer && (
              <div className="mt-5 rounded-2xl border border-accent-red/18 bg-accent-red/8 p-4 text-sm leading-6 text-ink-300">
                {result.disclaimer}
              </div>
            )}
          </div>
        </div>
      </div>

      <aside className="space-y-5">
        <div className="gold-shell animate-in rounded-[1.8rem]">
          <div className="gold-core h-full rounded-[1.45rem] p-5">
            <h3 className="text-lg font-semibold text-ink-50">Features used</h3>
            {features.length > 0 ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {features.map((feature) => (
                  <span key={feature} className="rounded-full border border-line-soft bg-white/[0.035] px-3 py-1.5 text-xs font-semibold text-ink-300">
                    {feature}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink-400">No feature list returned by backend.</p>
            )}
          </div>
        </div>
        <RecommendedPredictionSettings settings={result.recommended_settings} />
        <BackendNotes notes={notes} />
      </aside>
    </section>
  );
}

function SelectGroup({ label, value, options, onChange }) {
  const optionGridClass = options.length === 4 ? "grid-cols-4" : "grid-cols-3";

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">{label}</p>
      <div className={`mt-2 grid ${optionGridClass} gap-1.5 rounded-[1.25rem] border border-line-soft bg-surface-950 p-1.5`}>
        {options.map((option) => (
          <button
            key={option}
            onClick={() => onChange(option)}
            className={`min-h-10 min-w-0 rounded-2xl px-2 text-[11px] font-semibold transition-all duration-700 ease-premium ${
              String(value) === String(option) ? "bg-accent-gold text-surface-950" : "text-ink-300 hover:bg-white/[0.04] hover:text-ink-50"
            }`}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">{label}</p>
      <div className="number-font mt-2 flex min-h-[52px] items-center rounded-[1.25rem] border border-line-soft bg-surface-950 px-4 text-sm font-semibold text-ink-50">
        {value}
      </div>
    </div>
  );
}

function MarketSummary({ result }) {
  const market = result?.market || {};
  const values = [
    ["Price", result?.price],
    ["Market cap", market.market_cap],
    ["24h volume", market.volume_24h],
    ["24h change", market.change_24h_percent],
  ];

  return (
    <aside className="gold-shell rounded-[1.8rem]">
      <div className="gold-core rounded-[1.45rem] p-5">
        <h3 className="text-lg font-semibold text-ink-50">Market snapshot</h3>
        <div className="mt-4 grid gap-3">
          {values.map(([label, value]) => (
            <MetricRow key={label} label={label} value={formatMetric(value)} />
          ))}
        </div>
      </div>
    </aside>
  );
}

function AnalysisRoutePanel({ result }) {
  const contextItems = [
    ["News Included", result?.news_context_included ?? result?.included_news_context],
    ["RAG Included", result?.rag_context_included ?? result?.included_rag_context],
    ["DeFiLlama Included", result?.defillama_context_included ?? result?.included_defillama_context],
  ];
  const modelUsed = result?.model_used || result?.model || "N/A";
  const selectedModel = result?.selected_model || result?.llm_model || "";

  return (
    <aside className="gold-shell rounded-[1.8rem]">
      <div className="gold-core rounded-[1.45rem] p-5">
        <h3 className="text-lg font-semibold text-ink-50">Runtime context</h3>
        <div className="mt-4 grid gap-3">
          <MetricRow label="Context Strategy" value="Smart Context Selection" />
          <MetricRow label="Selected Model" value={modelUsed} />
          <MetricRow label="Response Mode" value={result?.response_mode || result?.generation_mode || "N/A"} />
          <MetricRow label="Prompt Context Type" value={result?.prompt_context_type || "N/A"} />
          <MetricRow label="Fallback Used" value={result?.fallback_happened ? "yes" : "no"} />
        </div>
        {selectedModel && selectedModel !== modelUsed && (
          <p className="mt-3 text-xs leading-5 text-ink-400">Attempted Ollama model: {selectedModel}</p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          {contextItems.map(([label, included]) => (
            <span
              key={label}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${
                included ? "border-accent-green/22 bg-accent-green/10 text-accent-green" : "border-line-soft bg-white/[0.025] text-ink-400"
              }`}
            >
              {label}: {included ? "yes" : "no"}
            </span>
          ))}
        </div>
      </div>
    </aside>
  );
}

function IndicatorGrid({ indicators }) {
  return (
    <aside className="gold-shell rounded-[1.8rem]">
      <div className="gold-core rounded-[1.45rem] p-5">
        <h3 className="text-lg font-semibold text-ink-50">Technical signals</h3>
        {indicators.length > 0 ? (
          <div className="mt-4 space-y-3">
            {indicators.map((item) => (
              <div key={item.name} className="rounded-2xl border border-line-cool bg-white/[0.025] p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-ink-50">{item.name}</p>
                    <p className="mt-1 text-xs text-ink-400">{item.note}</p>
                  </div>
                  <p className={`number-font text-sm font-semibold ${item.tone === "positive" ? "text-accent-green" : "text-accent-champagne"}`}>{item.value}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-ink-400">No indicator object returned by backend.</p>
        )}
      </div>
    </aside>
  );
}

function SourceTrace({ result, embedded = false }) {
  const sources = normalizeSources(result);
  const content = (
    <>
      <h3 className={embedded ? "text-sm font-semibold text-ink-50" : "text-lg font-semibold text-ink-50"}>Retrieved sources</h3>
      {sources.length > 0 ? (
        <div className="mt-4 space-y-3">
          {sources.map((source) => (
            <div key={`${source.title}-${source.type}`} className="rounded-2xl border border-line-cool bg-white/[0.04] p-4">
              <p className="text-sm font-semibold text-ink-50">{source.title}</p>
              <p className="mt-1 text-xs font-medium text-ink-300">
                {source.type}{source.extension ? ` ${source.extension}` : ""}{source.page ? ` - page ${source.page}` : ""}
              </p>
              {source.preview && (
                <p className="mt-3 rounded-xl border border-accent-gold/18 bg-white/[0.075] px-4 py-3 text-sm font-medium leading-7 text-ink-50">
                  {source.preview}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-ink-400">No source trace returned by backend.</p>
      )}
    </>
  );

  if (embedded) {
    return <div className="mt-5 rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5">{content}</div>;
  }

  return (
    <aside className="gold-shell rounded-[1.8rem]">
      <div className="gold-core rounded-[1.45rem] p-5">{content}</div>
    </aside>
  );
}

function ProbabilityCard({ label, value, tone }) {
  const percent = value === null ? null : Math.round(value * 100);
  const width = percent === null ? 0 : Math.max(0, Math.min(100, percent));
  const color = tone === "up" ? "bg-accent-green" : "bg-accent-red";
  return (
    <div className="rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-ink-50">{label}</p>
        <p className="number-font text-xl font-semibold text-ink-50">{percent === null ? "N/A" : `${percent}%`}</p>
      </div>
      <div className="mt-4 h-2 rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${color} transition-all duration-700 ease-premium`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="rounded-2xl border border-line-cool bg-white/[0.025] p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-ink-500">{label}</p>
      <p className="number-font mt-2 text-lg font-semibold text-ink-50">{value}</p>
    </div>
  );
}

function BaselinePanel({ metrics, baseline }) {
  const improvement = toNullableNumber(metrics.model_vs_baseline_improvement);
  const outperformed = improvement !== null && improvement > 0;
  return (
    <div className="rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-ink-50">Baseline comparison</p>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${outperformed ? "border-accent-green/22 bg-accent-green/10 text-accent-green" : "border-accent-red/22 bg-accent-red/10 text-accent-red"}`}>
          {outperformed ? "outperformed" : "not above baseline"}
        </span>
      </div>
      <div className="mt-4 grid gap-3">
        <MetricRow label="Model accuracy" value={formatPercent(metrics.model_accuracy ?? metrics.accuracy)} />
        <MetricRow label="Baseline accuracy" value={formatPercent(metrics.baseline_accuracy ?? baseline.baseline_accuracy)} />
        <MetricRow label="Improvement" value={formatSignedPercent(improvement)} />
        <MetricRow label="Majority baseline" value={formatPercent(baseline.majority_class_accuracy)} />
        <MetricRow label="Previous direction" value={formatPercent(baseline.previous_direction_accuracy)} />
      </div>
    </div>
  );
}

function ModelComparisonPanel({ candidates, selectedModel }) {
  if (!candidates.length) {
    return null;
  }

  return (
    <div className="mt-6 rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-ink-50">Machine learning model comparison</p>
          <p className="mt-1 text-xs leading-5 text-ink-400">All candidates use the same chronological train/test split; the backend selects the highest test accuracy.</p>
        </div>
        <span className="rounded-full border border-accent-gold/24 bg-accent-gold/10 px-3 py-1 text-xs font-semibold text-accent-gold">
          Best: {selectedModel || "N/A"}
        </span>
      </div>
      <div className="mt-4 overflow-hidden rounded-2xl border border-line-cool">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.035] text-xs uppercase tracking-[0.14em] text-ink-500">
            <tr>
              <th className="px-3 py-3 text-left">Model</th>
              <th className="px-3 py-3 text-right">Accuracy</th>
              <th className="px-3 py-3 text-right">F1</th>
              <th className="px-3 py-3 text-right">Vs baseline</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-cool">
            {candidates.map((candidate) => {
              const modelName = candidate.model_name || "Unknown";
              const selected = Boolean(candidate.selected) || modelName === selectedModel;
              return (
                <tr key={modelName} className={selected ? "bg-accent-gold/8" : ""}>
                  <td className="px-3 py-3">
                    <span className="font-semibold text-ink-50">{modelName}</span>
                    {selected && <span className="ml-2 rounded-full border border-accent-green/22 bg-accent-green/10 px-2 py-0.5 text-[11px] font-semibold text-accent-green">selected</span>}
                  </td>
                  <td className="number-font px-3 py-3 text-right text-ink-200">{formatPercent(candidate.accuracy)}</td>
                  <td className="number-font px-3 py-3 text-right text-ink-200">{formatPercent(candidate.f1)}</td>
                  <td className="number-font px-3 py-3 text-right text-ink-200">{formatSignedPercent(toNullableNumber(candidate.model_vs_baseline_improvement))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ConfusionMatrixPanel({ confusion, support }) {
  const labels = Array.isArray(confusion.labels) ? confusion.labels : ["DOWN", "UP"];
  const matrix = Array.isArray(confusion.matrix) ? confusion.matrix : [];
  return (
    <div className="rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5">
      <p className="text-sm font-semibold text-ink-50">Confusion matrix</p>
      {matrix.length === 2 ? (
        <div className="mt-4 overflow-hidden rounded-2xl border border-line-cool">
          <table className="w-full text-sm">
            <thead className="bg-white/[0.035] text-xs uppercase tracking-[0.14em] text-ink-500">
              <tr>
                <th className="px-3 py-3 text-left">Actual \\ Pred</th>
                {labels.map((label) => (
                  <th key={label} className="px-3 py-3 text-right">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line-cool">
              {matrix.map((row, index) => (
                <tr key={labels[index] || index}>
                  <td className="px-3 py-3 font-semibold text-ink-50">{labels[index] || `Class ${index}`}</td>
                  {row.map((value, cellIndex) => (
                    <td key={`${index}-${cellIndex}`} className="number-font px-3 py-3 text-right text-ink-200">{value}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 text-sm text-ink-400">No confusion matrix returned.</p>
      )}
      <div className="mt-4 grid grid-cols-3 gap-2">
        <MetricCard label="DOWN support" value={support.DOWN ?? "N/A"} />
        <MetricCard label="UP support" value={support.UP ?? "N/A"} />
        <MetricCard label="Total" value={support.total ?? "N/A"} />
      </div>
    </div>
  );
}

function RecommendedPredictionSettings({ settings }) {
  const resolved = isPlainObject(settings)
    ? settings
    : { symbol: "BTCUSDT", timeframes: ["4h", "1d"], limit: "300 daily candles for the public-provider demo", horizon_candles: "3 to 5 future candles" };
  return (
    <div className="rounded-[1.45rem] border border-line-soft bg-surface-900/90 p-5">
      <h3 className="text-lg font-semibold text-ink-50">Stable prediction settings</h3>
      <div className="mt-4 grid gap-3">
        <MetricRow label="Symbol" value={resolved.symbol || "BTCUSDT"} />
        <MetricRow label="Timeframe" value={Array.isArray(resolved.timeframes) ? resolved.timeframes.join(" or ") : resolved.timeframes || "4h or 1d"} />
        <MetricRow label="Limit" value={resolved.limit || "300 daily candles for the public-provider demo"} />
        <MetricRow label="Horizon" value={resolved.horizon_candles || "3 to 5 future candles"} />
      </div>
    </div>
  );
}

function BackendNotes({ notes }) {
  if (notes.length === 0) return null;
  return (
    <div className="rounded-[1.45rem] border border-line-soft bg-surface-900/90 p-5">
      <h3 className="text-lg font-semibold text-ink-50">Backend notes</h3>
      <div className="mt-4 space-y-3">
        {notes.map((note) => (
          <p key={note} className="rounded-2xl border border-line-cool bg-white/[0.025] p-4 text-sm leading-6 text-ink-300">{note}</p>
        ))}
      </div>
    </div>
  );
}

function MetricRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-line-cool bg-white/[0.045] px-4 py-3">
      <span className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-300">{label}</span>
      <span className="number-font text-sm font-semibold text-ink-50">{value}</span>
    </div>
  );
}

function EmptyPanel({ title, body, icon }) {
  return (
    <section className="flex items-center gap-4 rounded-[1.45rem] border border-line-soft bg-surface-900/88 px-5 py-4">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl border border-accent-gold/22 bg-accent-gold/10 text-accent-gold">
        <Icon name={icon} className="h-5 w-5" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-ink-50">{title}</h2>
        <p className="mt-1 text-sm text-ink-300">{body}</p>
      </div>
    </section>
  );
}

function LoadingPanel({ title }) {
  return (
    <section className="rounded-[1.45rem] border border-line-soft bg-surface-900/88 px-5 py-4">
      <div className="flex items-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-accent-gold/20 border-t-accent-gold" />
        <div>
          <h2 className="text-xl font-semibold text-ink-50">{title}</h2>
          <p className="mt-1 text-sm text-ink-300">The final UI is waiting for backend JSON instead of generating local fallback data.</p>
        </div>
      </div>
    </section>
  );
}

function ModeBadge({ label }) {
  return (
    <span className="rounded-full border border-accent-green/22 bg-accent-green/10 px-3 py-1 text-xs font-semibold text-accent-green">
      {label}
    </span>
  );
}

function normalizeIndicators(result) {
  if (!isPlainObject(result?.indicators)) return [];
  const indicators = result.indicators;
  return [
    { name: "RSI", value: formatValue(indicators.rsi, 2), note: "Relative strength index", tone: "neutral" },
    { name: "EMA 20 / 50 / 200", value: `${formatValue(indicators.ema_20, 2)} / ${formatValue(indicators.ema_50, 2)} / ${formatValue(indicators.ema_200, 2)}`, note: "Moving-average structure", tone: "positive" },
    { name: "MACD Hist.", value: formatValue(indicators.macd_histogram, 4), note: "Momentum confirmation", tone: Number(indicators.macd_histogram) >= 0 ? "positive" : "neutral" },
    { name: "BB Width", value: formatValue(indicators.bollinger_bandwidth, 4), note: "Volatility range", tone: "neutral" },
    { name: "Support / Resistance", value: `${formatValue(indicators.support_20, 2)} / ${formatValue(indicators.resistance_20, 2)}`, note: "Recent 20-candle range", tone: "neutral" },
  ];
}

function normalizeSources(result) {
  const retrieved = result?.retrieved_sources || result?.sources || [];
  if (!Array.isArray(retrieved)) return [];
  return retrieved.map((source, index) => {
    if (isPlainObject(source)) {
      return {
        title: source.source_name || source.source_path || source.title || `Source ${index + 1}`,
        type: source.source_type || source.type || "Retrieved source",
        extension: source.file_extension || source.extension || "",
        page: source.page,
        preview: source.preview || "",
      };
    }
    return { title: String(source), type: `Source ${index + 1}` };
  });
}

function asArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function toNullableNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatValue(value, digits) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "N/A";
  return Number(value).toFixed(digits);
}

function formatMetric(value) {
  if (value === undefined || value === null || value === "") return "N/A";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  const abs = Math.abs(number);
  if (abs >= 1_000_000_000_000) return `${(number / 1_000_000_000_000).toFixed(2)}T`;
  if (abs >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${(number / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${(number / 1_000).toFixed(2)}K`;
  return number.toFixed(2);
}

function formatPercent(value) {
  const number = toNullableNumber(value);
  if (number === null) return "N/A";
  return `${(number * 100).toFixed(1)}%`;
}

function formatSignedPercent(value) {
  const number = toNullableNumber(value);
  if (number === null) return "N/A";
  const sign = number > 0 ? "+" : "";
  return `${sign}${(number * 100).toFixed(1)}%`;
}

function readStoredChatModel() {
  try {
    return window.localStorage.getItem(SELECTED_CHAT_MODEL_STORAGE_KEY) || RECOMMENDED_CHAT_MODEL;
  } catch {
    return RECOMMENDED_CHAT_MODEL;
  }
}

function readStoredProviderSettings() {
  try {
    const stored = window.localStorage.getItem(MODEL_PROVIDER_STORAGE_KEY);
    if (!stored) return DEFAULT_PROVIDER_SETTINGS;
    const parsed = JSON.parse(stored);
    return {
      ...DEFAULT_PROVIDER_SETTINGS,
      ...parsed,
      openaiApiKey: "",
      researchApiKey: "",
    };
  } catch {
    return DEFAULT_PROVIDER_SETTINGS;
  }
}

function writeStoredProviderSettings(settings) {
  try {
    const nonSensitiveSettings = {
      providerType: settings.providerType,
      remoteOllamaBaseUrl: settings.remoteOllamaBaseUrl,
      remoteModelName: settings.remoteModelName,
      researchApiEndpointUrl: settings.researchApiEndpointUrl,
      openaiBaseUrl: settings.openaiBaseUrl,
      openaiModelName: settings.openaiModelName,
    };
    window.localStorage.setItem(MODEL_PROVIDER_STORAGE_KEY, JSON.stringify(nonSensitiveSettings));
  } catch {
    // Ignore storage failures so the UI can still run in private or restricted browser contexts.
  }
}

function buildProviderConfig(settings, selectedChatModel) {
  if (!settings || settings.providerType === "local_ollama") return null;
  if (settings.providerType === "remote_ollama") {
    return {
      provider_type: "remote_ollama",
      base_url: settings.remoteOllamaBaseUrl.trim(),
      model_name: (settings.remoteModelName || selectedChatModel || "").trim(),
    };
  }
  if (settings.providerType === "openai_compatible") {
    return {
      provider_type: "openai_compatible",
      base_url: settings.openaiBaseUrl.trim(),
      api_key: settings.openaiApiKey,
      model_name: settings.openaiModelName.trim(),
    };
  }
  if (settings.providerType === "research_api") {
    return {
      provider_type: "research_api",
      base_url: settings.researchApiEndpointUrl.trim(),
      api_key: settings.researchApiKey,
      model_name: "remote-research-api",
    };
  }
  return {
    provider_type: settings.providerType,
  };
}

function describeActiveProviderModel(settings, selectedChatModel) {
  if (!settings || settings.providerType === "local_ollama") {
    return `Local Ollama / ${selectedChatModel || "Detect models first"}`;
  }
  if (settings.providerType === "remote_ollama") {
    return `Remote Ollama / ${settings.remoteModelName || "test connection first"}`;
  }
  if (settings.providerType === "openai_compatible") {
    return `OpenAI-compatible / ${settings.openaiModelName || "enter model name"}`;
  }
  if (settings.providerType === "research_api") {
    return "Remote Research API / remote-research-api";
  }
  return "Custom endpoint placeholder";
}

function chooseChatModel(currentModel, chatModels, backendDefaultModel) {
  if (!Array.isArray(chatModels) || chatModels.length === 0) return "";
  if (currentModel && chatModels.includes(currentModel)) return currentModel;
  if (chatModels.includes(RECOMMENDED_CHAT_MODEL)) return RECOMMENDED_CHAT_MODEL;
  if (backendDefaultModel && chatModels.includes(backendDefaultModel)) return backendDefaultModel;
  return chatModels[0];
}

async function requestBackend(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      signal: controller.signal,
      ...options,
    });
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error?.message || "Backend request failed");
    }
    return payload;
  } finally {
    window.clearTimeout(timeout);
  }
}

function formatBackendError(error) {
  if (error.name === "AbortError") {
    return "Backend request timed out.";
  }
  if (error.name === "TypeError") {
    return "Backend is not running or cannot be reached.";
  }
  return `Live backend request failed: ${error.message || "unknown error"}.`;
}

export default App;
