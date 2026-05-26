import { Icon } from "./icons";

const navItems = [
  { id: "insight", label: "Insight Engine", icon: "brain", description: "RAG + LLM answer" },
  { id: "prediction", label: "Prediction Engine", icon: "gauge", description: "Technical trend model" },
];

function Sidebar({ activeEngine, onEngineChange }) {
  return (
    <aside className="hidden w-[260px] shrink-0 flex-col border-r border-line-soft bg-surface-950/96 lg:flex">
      <div className="flex h-24 items-center gap-3 px-6">
        <div className="grid h-11 w-11 place-items-center rounded-2xl border border-accent-gold/30 bg-accent-gold/10 text-accent-gold shadow-glow">
          <Icon name="layers" className="h-5 w-5" />
        </div>
        <div>
          <span className="block text-lg font-semibold tracking-wide text-ink-50">Web3 Finance</span>
          <span className="text-[10px] font-semibold uppercase tracking-[0.28em] text-accent-gold/80">LLM Analyzer</span>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-2 px-4">
        {navItems.map((item) => {
          const active = activeEngine === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onEngineChange(item.id)}
              className={`group rounded-2xl px-4 py-4 text-left transition-all duration-700 ease-premium ${
                active
                  ? "border border-accent-gold/28 bg-accent-gold/10 text-accent-champagne shadow-glow"
                  : "border border-transparent text-ink-300 hover:bg-white/[0.04] hover:text-ink-50"
              }`}
            >
              <span className="flex items-center gap-3 text-sm font-semibold">
                <Icon name={item.icon} className="h-5 w-5 transition-transform duration-700 ease-premium group-hover:translate-x-0.5" />
                {item.label}
              </span>
              <span className="mt-2 block pl-8 text-xs leading-5 text-ink-400">{item.description}</span>
            </button>
          );
        })}
      </nav>

      <div className="border-t border-line-soft p-4">
        <div className="rounded-[1.35rem] border border-accent-red/20 bg-accent-red/8 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-red">Academic Use</p>
          <p className="mt-3 text-sm leading-6 text-ink-300">Outputs are explanatory demo results, not financial advice.</p>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
