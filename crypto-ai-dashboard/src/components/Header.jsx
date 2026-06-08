import { Icon } from "./icons";

function Header({ activeEngine, onEngineChange, backendStatus, onCheckBackend }) {
  return (
    <header className="border-b border-line-soft bg-surface-950/86 px-4 py-5 backdrop-blur-xl sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-accent-gold/80">Web3 Finance LLM</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-normal text-ink-50 sm:text-3xl">
            Crypto Market Insight Workspace
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-300">
            Ask market questions, retrieve source-grounded context, and run short-term trend prediction in one clean interface.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="grid grid-cols-3 gap-2 rounded-full border border-line-soft bg-surface-950 p-1.5">
            <EngineButton testId="engine-insight" active={activeEngine === "insight"} icon="brain" label="Insight" onClick={() => onEngineChange("insight")} />
            <EngineButton testId="engine-prediction" active={activeEngine === "prediction"} icon="gauge" label="Predict" onClick={() => onEngineChange("prediction")} />
            <EngineButton testId="engine-models" active={activeEngine === "models"} icon="layers" label="Settings" onClick={() => onEngineChange("models")} />
          </div>
          <button data-testid="check-backend" onClick={onCheckBackend} className="ghost-button flex items-center justify-center gap-2 text-sm">
            <span className={`h-2 w-2 rounded-full ${backendStatus === "online" ? "bg-accent-green" : backendStatus === "checking" ? "bg-accent-gold" : "bg-accent-red"}`} />
            {backendStatus === "online" ? "Backend online" : backendStatus === "checking" ? "Checking..." : "Check backend"}
          </button>
        </div>
      </div>
    </header>
  );
}

function EngineButton({ active, icon, label, onClick, testId }) {
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      className={`flex h-11 items-center justify-center gap-2 rounded-full px-4 text-sm font-semibold transition-all duration-700 ease-premium ${
        active ? "bg-accent-gold text-surface-950 shadow-glow" : "text-ink-300 hover:bg-white/[0.04] hover:text-ink-50"
      }`}
    >
      <Icon name={icon} className="h-4 w-4" />
      {label}
    </button>
  );
}

export default Header;
