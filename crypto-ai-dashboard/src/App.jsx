import { useMemo, useState } from "react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import { sampleQueries, symbols, timeframes } from "./data/marketData";
import { Icon } from "./components/icons";

const API_BASE_URL = "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 180000;

function App() {
  const [activeEngine, setActiveEngine] = useState("insight");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [horizonDays, setHorizonDays] = useState(3);
  const [question, setQuestion] = useState(sampleQueries[0].question);
  const [insightResult, setInsightResult] = useState(null);
  const [predictionResult, setPredictionResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [backendStatus, setBackendStatus] = useState("idle");

  async function checkBackend() {
    setBackendStatus("checking");
    setNotice("");
    try {
      await requestBackend("/health");
      setBackendStatus("online");
    } catch (error) {
      setBackendStatus("offline");
      setNotice(formatBackendError(error));
    }
  }

  async function runInsight() {
    setActiveEngine("insight");
    setLoading(true);
    setNotice("");
    setInsightResult(null);
    try {
      const payload = await requestBackend("/analyze", {
        method: "POST",
        body: JSON.stringify({ symbol, timeframe, limit: 120, question }),
      });
      setInsightResult({ ...payload.data, sources: payload.sources || [] });
      setBackendStatus("online");
    } catch (error) {
      setNotice(`${formatBackendError(error)} No frontend fallback result was generated.`);
      setBackendStatus(error.name === "TypeError" || error.name === "AbortError" ? "offline" : "online");
    } finally {
      setLoading(false);
    }
  }

  async function runPrediction() {
    setActiveEngine("prediction");
    setLoading(true);
    setNotice("");
    setPredictionResult(null);
    try {
      const payload = await requestBackend("/predict", {
        method: "POST",
        body: JSON.stringify({ symbol, timeframe, horizon_days: Number(horizonDays), limit: 300 }),
      });
      setPredictionResult({ ...payload.data, sources: payload.sources || [] });
      setBackendStatus("online");
    } catch (error) {
      setNotice(`${formatBackendError(error)} No frontend fallback result was generated.`);
      setBackendStatus(error.name === "TypeError" || error.name === "AbortError" ? "offline" : "online");
    } finally {
      setLoading(false);
    }
  }

  const activeTitle = activeEngine === "insight" ? "Insight Engine" : "Prediction Engine";

  return (
    <div className="min-h-screen bg-surface-950 text-ink-50">
      <div className="pointer-events-none fixed inset-0 z-0 opacity-[0.03] [background-image:radial-gradient(circle_at_1px_1px,#f7f1e3_1px,transparent_0)] [background-size:24px_24px]" />
      <div className="relative z-10 flex min-h-screen">
        <Sidebar activeEngine={activeEngine} onEngineChange={setActiveEngine} />

        <main className="min-w-0 flex-1">
          <Header activeEngine={activeEngine} onEngineChange={setActiveEngine} backendStatus={backendStatus} onCheckBackend={checkBackend} />

          <section className="mx-auto flex w-full max-w-[1180px] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
            <MobileEngineSwitch activeEngine={activeEngine} onEngineChange={setActiveEngine} />

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
              <WorkspaceCard
                activeEngine={activeEngine}
                activeTitle={activeTitle}
                symbol={symbol}
                setSymbol={setSymbol}
                timeframe={timeframe}
                setTimeframe={setTimeframe}
                horizonDays={horizonDays}
                setHorizonDays={setHorizonDays}
                question={question}
                setQuestion={setQuestion}
                loading={loading}
                onRunInsight={runInsight}
                onRunPrediction={runPrediction}
              />

              <QuickPanel
                activeEngine={activeEngine}
                setActiveEngine={setActiveEngine}
                setSymbol={setSymbol}
                setQuestion={setQuestion}
                onRunInsight={runInsight}
                onRunPrediction={runPrediction}
                loading={loading}
                question={question}
              />
            </div>

            {notice && (
              <div className="rounded-2xl border border-accent-gold/22 bg-accent-gold/8 px-4 py-3 text-sm leading-6 text-accent-champagne">
                {notice}
              </div>
            )}

            {activeEngine === "insight" ? (
              <InsightResults result={insightResult} loading={loading} />
            ) : (
              <PredictionResults result={predictionResult} loading={loading} />
            )}
          </section>
        </main>
      </div>
    </div>
  );
}

function MobileEngineSwitch({ activeEngine, onEngineChange }) {
  return (
    <div className="grid grid-cols-2 gap-2 rounded-full border border-line-soft bg-surface-950 p-1.5 lg:hidden">
      {[
        ["insight", "Insight Engine"],
        ["prediction", "Prediction Engine"],
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

  return (
    <section className="gold-shell animate-in rounded-[1.8rem]">
      <div className="gold-core rounded-[1.45rem] p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-gold/85">{props.activeTitle}</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink-50">
              {isInsight ? "Ask a source-grounded market question" : "Run backend trend prediction"}
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

        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <SelectGroup label="Symbol" value={props.symbol} options={symbols} onChange={props.setSymbol} />
          <SelectGroup label="Timeframe" value={props.timeframe} options={timeframes} onChange={props.setTimeframe} />
          {isInsight ? (
            <ReadOnlyField label="Candle limit" value="120" />
          ) : (
            <SelectGroup label="Horizon" value={String(props.horizonDays)} options={["1", "3", "7", "14"]} onChange={(value) => props.setHorizonDays(Number(value))} />
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

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
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
            onClick={() => {
              props.setQuestion(sampleQueries[0].question);
              props.setSymbol("BTCUSDT");
            }}
            className="ghost-button h-12 text-sm"
          >
            Reset input
          </button>
        </div>
      </div>
    </section>
  );
}

function QuickPanel({ activeEngine, setActiveEngine, setSymbol, setQuestion, onRunInsight, onRunPrediction, loading, question }) {
  return (
    <aside className="space-y-4">
      <div className="gold-shell rounded-[1.8rem]">
        <div className="gold-core rounded-[1.45rem] p-5">
          <h3 className="text-lg font-semibold text-ink-50">Quick examples</h3>
          <p className="mt-1 text-sm text-ink-300">Fill the workspace, then run the backend call.</p>
          <div className="mt-4 space-y-2">
            {sampleQueries.map((item) => (
              <button
                data-testid={`example-${item.engine}-${item.symbol}`}
                key={item.label}
                onClick={() => {
                  setActiveEngine(item.engine);
                  setSymbol(item.symbol);
                  setQuestion(item.question);
                }}
                className="w-full rounded-2xl border border-line-soft bg-white/[0.025] p-4 text-left transition-all duration-700 ease-premium hover:border-line-strong hover:bg-white/[0.045]"
              >
                <span className="block text-sm font-semibold text-ink-50">{item.label}</span>
                <span className="mt-1 block text-xs leading-5 text-ink-400">{item.question}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-[1.45rem] border border-line-soft bg-surface-900/90 p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-gold/85">Unified backend contract</p>
        <div className="mt-4 grid gap-3">
          <EngineMiniCard active={activeEngine === "insight"} title="Insight Engine" body="POST /analyze" icon="brain" onClick={() => setActiveEngine("insight")} />
          <EngineMiniCard active={activeEngine === "prediction"} title="Prediction Engine" body="POST /predict" icon="gauge" onClick={() => setActiveEngine("prediction")} />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button data-testid="quick-run-insight" disabled={loading || !question.trim()} onClick={onRunInsight} className="ghost-button text-xs disabled:cursor-not-allowed disabled:opacity-50">Run insight</button>
          <button data-testid="quick-run-predict" disabled={loading} onClick={onRunPrediction} className="ghost-button text-xs disabled:cursor-not-allowed disabled:opacity-50">Run predict</button>
        </div>
      </div>
    </aside>
  );
}

function InsightResults({ result, loading }) {
  const indicators = useMemo(() => normalizeIndicators(result), [result]);
  const riskFlags = asArray(result?.risk_flags || result?.riskFlags);

  if (loading) return <LoadingPanel title="Waiting for FastAPI /analyze..." />;
  if (!result) return <EmptyPanel title="No backend insight yet" body="Choose a symbol, write a question, then run Insight Analysis." icon="brain" />;

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
          <p className="mt-5 rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5 text-sm leading-8 text-ink-200">
            {result.answer || "The backend response did not include an answer field."}
          </p>
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
        <IndicatorGrid indicators={indicators} />
        <SourceTrace result={result} />
      </div>
    </section>
  );
}

function PredictionResults({ result, loading }) {
  if (loading) return <LoadingPanel title="Waiting for FastAPI /predict..." />;
  if (!result) return <EmptyPanel title="No backend prediction yet" body="Choose symbol, timeframe and horizon, then run Prediction." icon="gauge" />;

  const up = toNullableNumber(result.probability_up ?? result.probabilityUp);
  const down = toNullableNumber(result.probability_down ?? result.probabilityDown);
  const metrics = isPlainObject(result.metrics) ? result.metrics : {};
  const features = asArray(result.features);
  const notes = asArray(result.notes);

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="gold-shell animate-in rounded-[1.8rem]">
        <div className="gold-core rounded-[1.45rem] p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-gold/85">FastAPI /predict</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink-50">{result.symbol || "Market"} Trend: {result.predicted_trend || result.trend || "N/A"}</h2>
            </div>
            <ModeBadge label="Live backend" />
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <ProbabilityCard label="Probability UP" value={up} tone="up" />
            <ProbabilityCard label="Probability DOWN" value={down} tone="down" />
          </div>

          <div className="mt-6 rounded-[1.25rem] border border-line-soft bg-surface-950/80 p-5">
            <p className="text-sm font-semibold text-ink-50">Model evidence</p>
            {Object.keys(metrics).length > 0 ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-4">
                {Object.entries(metrics).map(([key, value]) => (
                  <div key={key} className="rounded-2xl border border-line-cool bg-white/[0.025] p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-ink-500">{key}</p>
                    <p className="number-font mt-2 text-lg font-semibold text-ink-50">{String(value)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink-400">No metrics object returned by backend.</p>
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
            {result.disclaimer && (
              <div className="mt-5 rounded-2xl border border-accent-red/18 bg-accent-red/8 p-4 text-sm leading-6 text-ink-300">
                {result.disclaimer}
              </div>
            )}
          </div>
        </div>
        <BackendNotes notes={notes} />
      </aside>
    </section>
  );
}

function SelectGroup({ label, value, options, onChange }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-400">{label}</p>
      <div className="mt-2 grid grid-cols-3 gap-2 rounded-[1.25rem] border border-line-soft bg-surface-950 p-1.5">
        {options.map((option) => (
          <button
            key={option}
            onClick={() => onChange(option)}
            className={`min-h-10 rounded-2xl px-3 text-xs font-semibold transition-all duration-700 ease-premium ${
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

function EngineMiniCard({ active, title, body, icon, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-2xl border p-4 text-left transition-all duration-700 ease-premium ${
        active ? "border-accent-gold/30 bg-accent-gold/10" : "border-line-soft bg-white/[0.025] hover:border-line-strong"
      }`}
    >
      <span className="flex items-center gap-3 text-sm font-semibold text-ink-50">
        <Icon name={icon} className="h-5 w-5 text-accent-gold" />
        {title}
      </span>
      <span className="mt-2 block text-xs leading-5 text-ink-400">{body}</span>
    </button>
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

function SourceTrace({ result }) {
  const sources = normalizeSources(result);
  return (
    <aside className="gold-shell rounded-[1.8rem]">
      <div className="gold-core rounded-[1.45rem] p-5">
        <h3 className="text-lg font-semibold text-ink-50">Retrieved sources</h3>
        {sources.length > 0 ? (
          <div className="mt-4 space-y-3">
            {sources.map((source) => (
              <div key={`${source.title}-${source.type}`} className="rounded-2xl border border-line-cool bg-white/[0.025] p-4">
                <p className="text-sm font-semibold text-ink-50">{source.title}</p>
                <p className="mt-1 text-xs text-ink-400">{source.type}{source.page ? ` - page ${source.page}` : ""}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-ink-400">No source trace returned by backend.</p>
        )}
      </div>
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
    <div className="flex items-center justify-between rounded-2xl border border-line-cool bg-white/[0.025] px-4 py-3">
      <span className="text-xs uppercase tracking-[0.16em] text-ink-500">{label}</span>
      <span className="number-font text-sm font-semibold text-ink-50">{value}</span>
    </div>
  );
}

function EmptyPanel({ title, body, icon }) {
  return (
    <section className="rounded-[1.8rem] border border-line-soft bg-surface-900/88 p-8 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl border border-accent-gold/22 bg-accent-gold/10 text-accent-gold">
        <Icon name={icon} className="h-5 w-5" />
      </div>
      <h2 className="mt-4 text-xl font-semibold text-ink-50">{title}</h2>
      <p className="mt-2 text-sm text-ink-300">{body}</p>
    </section>
  );
}

function LoadingPanel({ title }) {
  return (
    <section className="rounded-[1.8rem] border border-line-soft bg-surface-900/88 p-8">
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
    { name: "EMA 20 / 50", value: `${formatValue(indicators.ema_20, 2)} / ${formatValue(indicators.ema_50, 2)}`, note: "Moving-average structure", tone: "positive" },
    { name: "MACD Hist.", value: formatValue(indicators.macd_histogram, 4), note: "Momentum confirmation", tone: Number(indicators.macd_histogram) >= 0 ? "positive" : "neutral" },
    { name: "BB Width", value: formatValue(indicators.bollinger_bandwidth, 4), note: "Volatility range", tone: "neutral" },
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
        page: source.page,
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
