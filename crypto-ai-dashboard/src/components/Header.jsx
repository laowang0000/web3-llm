function Header({ backendStatus, onCheckBackend }) {
  return (
    <header className="border-b border-line-soft bg-surface-950/86 px-4 py-5 backdrop-blur-xl sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.32em] text-accent-gold/90">Web3 Finance LLM</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-normal text-ink-50 sm:text-3xl">
            Crypto Market Insight Workspace
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-300">
            Ask market questions, inspect retrieved evidence, and run short-term trend prediction in one clean interface.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <button data-testid="check-backend" onClick={onCheckBackend} className="ghost-button flex items-center justify-center gap-2 text-sm">
            <span className={`h-2 w-2 rounded-full ${backendStatus === "online" ? "bg-accent-green" : backendStatus === "checking" ? "bg-accent-gold" : "bg-accent-red"}`} />
            {backendStatus === "online" ? "Backend online" : backendStatus === "checking" ? "Checking..." : "Check backend"}
          </button>
        </div>
      </div>
    </header>
  );
}

export default Header;
