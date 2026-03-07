import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, RefreshCw, Users, Scale, Crown, Zap, AlertTriangle } from "lucide-react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { Skeleton } from "../components/shared/Skeleton";
import { useAnalysisOverview } from "../hooks/useAnalysisOverview";
import {
  useTriggerData,
  useTriggerAgents,
  useTriggerVerdict,
  useTriggerBoard,
  useTriggerFull,
} from "../hooks/usePipelineTrigger";
import type { AnalysisOverviewTicker, AnalysisOverviewAgent } from "../types/models";

// ─── Utilities ────────────────────────────────────────────────────────────

type Scope = "portfolio" | "watchlist" | "recommendations" | "custom";

function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

const DATA_SOURCE_LABELS: Record<string, string> = {
  fundamentals: "Fundamentals",
  technical_indicators: "Technicals",
  macro_context: "Macro",
  news_context: "News",
  earnings_context: "Earnings",
  insider_context: "Insider",
  filing_context: "Filings",
  institutional_context: "Institutional",
  analyst_ratings: "Analyst Ratings",
  short_interest: "Short Interest",
  social_sentiment: "Social",
  research_briefing: "Research",
};

function verdictVariant(v: string | null): "success" | "error" | "warning" | "accent" | "neutral" {
  if (!v) return "neutral";
  if (v === "STRONG_BUY" || v === "BUY" || v === "ACCUMULATE") return "success";
  if (v === "SELL" || v === "AVOID" || v === "REJECT" || v === "DISCARD") return "error";
  if (v === "REDUCE") return "error";
  if (v === "HOLD") return "warning";
  if (v === "WATCHLIST") return "accent";
  return "neutral";
}

function stalenessColor(s: string): string {
  if (s === "fresh") return "var(--color-success)";
  if (s === "partial") return "var(--color-warning)";
  return "var(--color-error)";
}

const categoryLabels: Record<string, string> = {
  portfolio: "Portfolio",
  watchlist: "Watchlist",
  recommendation: "Pick",
  other: "",
};

// ─── Filter Bar ───────────────────────────────────────────────────────────

function FilterBar({
  scope,
  onScopeChange,
  customTickers,
  onCustomTickersChange,
}: {
  scope: Scope;
  onScopeChange: (s: Scope) => void;
  customTickers: string[];
  onCustomTickersChange: (t: string[]) => void;
}) {
  const [input, setInput] = useState("");

  const chips: { key: Scope; label: string }[] = [
    { key: "portfolio", label: "Portfolio" },
    { key: "recommendations", label: "Picks" },
    { key: "watchlist", label: "Watchlist" },
    { key: "custom", label: "Custom" },
  ];

  const addTicker = () => {
    const t = input.trim().toUpperCase();
    if (t && !customTickers.includes(t)) {
      onCustomTickersChange([...customTickers, t]);
    }
    setInput("");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
      <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
        {chips.map((c) => (
          <button
            key={c.key}
            onClick={() => onScopeChange(c.key)}
            style={{
              padding: "6px 14px",
              fontSize: "var(--text-xs)",
              fontWeight: scope === c.key ? 600 : 400,
              color: scope === c.key ? "#fff" : "var(--color-text-muted)",
              background: scope === c.key ? "var(--gradient-active)" : "var(--color-surface-1)",
              border: scope === c.key ? "none" : "1px solid var(--glass-border)",
              borderRadius: "var(--radius-full)",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {c.label}
          </button>
        ))}
      </div>

      {scope === "custom" && (
        <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "center" }}>
          <form
            onSubmit={(e) => { e.preventDefault(); addTicker(); }}
            style={{ display: "flex", gap: "var(--space-sm)", flex: 1 }}
          >
            <input
              type="text"
              placeholder="Enter ticker..."
              value={input}
              onChange={(e) => setInput(e.target.value.toUpperCase())}
              style={{
                flex: 1,
                padding: "var(--space-sm) var(--space-md)",
                background: "var(--color-surface-0)",
                border: "1px solid var(--glass-border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--color-text)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--text-sm)",
                outline: "none",
              }}
            />
            <button
              type="submit"
              disabled={!input.trim()}
              style={{
                padding: "var(--space-sm) var(--space-md)",
                background: input.trim() ? "var(--gradient-active)" : "var(--color-surface-2)",
                border: "none",
                borderRadius: "var(--radius-sm)",
                color: input.trim() ? "#fff" : "var(--color-text-muted)",
                fontSize: "var(--text-xs)",
                fontWeight: 600,
                cursor: input.trim() ? "pointer" : "not-allowed",
              }}
            >
              Add
            </button>
          </form>
          {customTickers.length > 0 && (
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {customTickers.map((t) => (
                <span
                  key={t}
                  onClick={() => onCustomTickersChange(customTickers.filter((x) => x !== t))}
                  style={{
                    padding: "2px 8px",
                    fontSize: 10,
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                    background: "var(--color-surface-1)",
                    border: "1px solid var(--glass-border)",
                    borderRadius: "var(--radius-full)",
                    color: "var(--color-text-secondary)",
                    cursor: "pointer",
                  }}
                  title="Click to remove"
                >
                  {t} ×
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Data Sources Grid ────────────────────────────────────────────────────

function DataSourcesGrid({ available, dataAge }: {
  available: Record<string, boolean>;
  dataAge: Record<string, string>;
}) {
  const keys = Object.keys(DATA_SOURCE_LABELS);

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(3, 1fr)",
      gap: "var(--space-xs)",
    }}>
      {keys.map((key) => {
        const has = available[key] ?? false;
        const age = dataAge[key];
        return (
          <div
            key={key}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 8px",
              background: "var(--color-surface-0)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--glass-border)",
            }}
          >
            <div style={{
              width: 6, height: 6, borderRadius: "var(--radius-full)", flexShrink: 0,
              background: has ? "var(--color-success)" : "var(--color-error)",
            }} />
            <span style={{ fontSize: 10, color: "var(--color-text-secondary)", flex: 1 }}>
              {DATA_SOURCE_LABELS[key] ?? key}
            </span>
            {age && (
              <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
                {formatRelativeTime(age)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Agent List ───────────────────────────────────────────────────────────

function AgentList({ agents }: { agents: AnalysisOverviewAgent[] }) {
  if (agents.length === 0) {
    return (
      <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", padding: "var(--space-sm) 0" }}>
        No agent signals yet
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {agents.map((a) => {
        const conf = a.confidence ?? 0;
        const confColor = conf >= 0.7 ? "var(--color-success)" : conf >= 0.4 ? "var(--color-warning)" : "var(--color-error)";
        return (
          <div key={a.name} style={{
            display: "flex", alignItems: "center", gap: "var(--space-sm)",
            padding: "3px var(--space-sm)", borderRadius: "var(--radius-sm)",
          }}>
            <span style={{ fontSize: 11, fontWeight: 600, minWidth: 80, color: "var(--color-text-secondary)" }}>
              {a.name.charAt(0).toUpperCase() + a.name.slice(1)}
            </span>
            {a.confidence != null && (
              <div style={{ flex: 1, display: "flex", alignItems: "center", gap: "var(--space-xs)" }}>
                <div style={{ flex: 1, height: 3, background: "var(--color-surface-2)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ width: `${conf * 100}%`, height: "100%", background: confColor, borderRadius: 2 }} />
                </div>
                <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: confColor, minWidth: 28 }}>
                  {Math.round(conf * 100)}%
                </span>
              </div>
            )}
            {a.status === "capped" && (
              <AlertTriangle size={10} style={{ color: "var(--color-warning)", flexShrink: 0 }} />
            )}
            <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)", flexShrink: 0 }}>
              {formatRelativeTime(a.ranAt)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Action Bar ───────────────────────────────────────────────────────────

function ActionBar({ ticker, onDone }: { ticker: string; onDone: () => void }) {
  const triggerData = useTriggerData();
  const triggerAgents = useTriggerAgents();
  const triggerVerdict = useTriggerVerdict();
  const triggerBoard = useTriggerBoard();
  const triggerFull = useTriggerFull();

  const [error, setError] = useState<string | null>(null);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      onDone();
    } catch (e) {
      setError(`${label}: ${e instanceof Error ? e.message : "failed"}`);
    }
  };

  const ALL_DATA_KEYS = Object.keys(DATA_SOURCE_LABELS);

  const actions = [
    {
      label: "Refresh Data",
      icon: RefreshCw,
      loading: triggerData.isPending,
      onClick: () => run("Data", () => triggerData.mutateAsync({ ticker, data_keys: ALL_DATA_KEYS })),
    },
    {
      label: "Run Agents",
      icon: Users,
      loading: triggerAgents.isPending,
      onClick: () => run("Agents", () => triggerAgents.mutateAsync({ ticker })),
    },
    {
      label: "Verdict",
      icon: Scale,
      loading: triggerVerdict.isPending,
      onClick: () => run("Verdict", () => triggerVerdict.mutateAsync({ ticker })),
    },
    {
      label: "Board",
      icon: Crown,
      loading: triggerBoard.isPending,
      onClick: () => run("Board", () => triggerBoard.mutateAsync({ ticker })),
    },
    {
      label: "Full Pipeline",
      icon: Zap,
      loading: triggerFull.isPending,
      onClick: () => run("Full", () => triggerFull.mutateAsync({ tickers: [ticker] })),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", gap: "var(--space-xs)", flexWrap: "wrap" }}>
        {actions.map((a) => (
          <button
            key={a.label}
            onClick={a.onClick}
            disabled={a.loading}
            style={{
              display: "flex", alignItems: "center", gap: 4,
              padding: "6px 10px",
              fontSize: 11, fontWeight: 600,
              background: "var(--color-surface-0)",
              border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)",
              color: a.loading ? "var(--color-text-muted)" : "var(--color-text-secondary)",
              cursor: a.loading ? "wait" : "pointer",
              transition: "all 0.15s ease",
              opacity: a.loading ? 0.6 : 1,
            }}
          >
            <a.icon size={12} style={a.loading ? { animation: "spin 1s linear infinite" } : undefined} />
            {a.label}
          </button>
        ))}
      </div>
      {error && (
        <div style={{ marginTop: "var(--space-xs)", fontSize: 11, color: "var(--color-error)" }}>
          {error}
        </div>
      )}
    </div>
  );
}

// ─── Ticker Card ──────────────────────────────────────────────────────────

function TickerAnalysisCard({
  ticker,
  expanded,
  onToggle,
  onRefresh,
}: {
  ticker: AnalysisOverviewTicker;
  expanded: boolean;
  onToggle: () => void;
  onRefresh: () => void;
}) {
  const displayVerdict = ticker.boardAdjustedVerdict || ticker.verdict;
  const catLabel = categoryLabels[ticker.category];

  return (
    <div style={{
      background: "var(--color-surface-1)",
      border: "1px solid var(--glass-border)",
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
    }}>
      {/* Header — always visible */}
      <button
        onClick={onToggle}
        style={{
          width: "100%", padding: "var(--space-md) var(--space-lg)",
          background: "none", border: "none", cursor: "pointer",
          textAlign: "left", color: "var(--color-text)", fontFamily: "var(--font-sans)",
        }}
      >
        {/* Row 1: Ticker + verdict + data pill + time */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
          <span style={{
            fontFamily: "var(--font-mono)", fontWeight: 700,
            fontSize: "var(--text-base)", minWidth: 52,
          }}>
            {ticker.ticker}
          </span>

          {displayVerdict && (
            <Badge variant={verdictVariant(displayVerdict)} size="sm">
              {displayVerdict}
            </Badge>
          )}

          {/* Data coverage pill */}
          <span style={{
            padding: "2px 8px", borderRadius: "var(--radius-full)",
            fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
            color: stalenessColor(ticker.dataStaleness),
            background: `${stalenessColor(ticker.dataStaleness)}15`,
            border: `1px solid ${stalenessColor(ticker.dataStaleness)}30`,
          }}>
            {ticker.dataSourceCount}/{ticker.dataSourceTotal} data
          </span>

          <div style={{ flex: 1 }} />

          {/* Agent count */}
          <span style={{
            fontSize: 10, fontFamily: "var(--font-mono)",
            color: ticker.agentCount === ticker.agentTotal ? "var(--color-success)" : "var(--color-text-muted)",
          }}>
            {ticker.agentCount}/{ticker.agentTotal} agents
          </span>

          {/* Last run */}
          <span style={{ fontSize: 10, color: "var(--color-text-muted)", minWidth: 50, textAlign: "right" }}>
            {formatRelativeTime(ticker.lastAgentRun)}
          </span>

          <motion.div
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            style={{ color: "var(--color-text-muted)", flexShrink: 0 }}
          >
            <ChevronDown size={14} />
          </motion.div>
        </div>

        {/* Row 2: Category + capped warning */}
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginTop: 4 }}>
          {catLabel && (
            <span style={{
              fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em",
              color: "var(--color-text-muted)",
            }}>
              {catLabel}
            </span>
          )}
          {ticker.verdictConfidence != null && (
            <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
              {Math.round(ticker.verdictConfidence * 100)}% conf
            </span>
          )}
          {ticker.cappedAgentCount > 0 && (
            <span style={{ fontSize: 10, color: "var(--color-warning)", display: "flex", alignItems: "center", gap: 3 }}>
              <AlertTriangle size={10} />
              {ticker.cappedAgentCount} capped
            </span>
          )}
          {ticker.verdictAt && (
            <span style={{ fontSize: 9, color: "var(--color-text-muted)" }}>
              verdict {formatRelativeTime(ticker.verdictAt)}
            </span>
          )}
        </div>
      </button>

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: "hidden" }}
          >
            <div style={{
              padding: "var(--space-sm) var(--space-lg) var(--space-lg)",
              borderTop: "1px solid var(--glass-border)",
              display: "flex", flexDirection: "column", gap: "var(--space-md)",
            }}>
              {/* Data Sources */}
              <div>
                <div style={{
                  fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)",
                  textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "var(--space-xs)",
                }}>
                  Data Sources
                </div>
                <DataSourcesGrid available={ticker.available} dataAge={ticker.dataAge} />
              </div>

              {/* Agent Signals */}
              <div>
                <div style={{
                  fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)",
                  textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "var(--space-xs)",
                }}>
                  Agent Signals
                </div>
                <AgentList agents={ticker.agents} />
              </div>

              {/* Actions */}
              <div>
                <div style={{
                  fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)",
                  textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "var(--space-xs)",
                }}>
                  Actions
                </div>
                <ActionBar ticker={ticker.ticker} onDone={onRefresh} />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Main View ────────────────────────────────────────────────────────────

export function Analyse() {
  const [scope, setScope] = useState<Scope>("portfolio");
  const [customTickers, setCustomTickers] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const { tickers, loading, error, refresh } = useAnalysisOverview(scope, customTickers);

  const toggleExpand = (t: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Analysis"
        subtitle="Run status & data freshness"
        right={
          tickers.length > 0 ? (
            <Badge variant="neutral">{tickers.length} tickers</Badge>
          ) : null
        }
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
        {/* Scope filter */}
        <FilterBar
          scope={scope}
          onScopeChange={setScope}
          customTickers={customTickers}
          onCustomTickersChange={setCustomTickers}
        />

        {/* Loading */}
        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            <Skeleton height={80} />
            <Skeleton height={80} />
            <Skeleton height={80} />
          </div>
        )}

        {/* Error */}
        {error && (
          <BentoCard variant="error">
            <p style={{ color: "var(--color-error)", fontSize: "var(--text-sm)" }}>{error}</p>
          </BentoCard>
        )}

        {/* Empty state */}
        {!loading && !error && tickers.length === 0 && (
          <BentoCard>
            <div style={{
              textAlign: "center", padding: "var(--space-xl) 0",
              color: "var(--color-text-muted)", fontSize: "var(--text-sm)",
            }}>
              {scope === "custom"
                ? "Add a ticker above to see its analysis status."
                : `No tickers in ${scope === "recommendations" ? "picks" : scope}.`}
            </div>
          </BentoCard>
        )}

        {/* Ticker cards */}
        {!loading && tickers.map((t) => (
          <TickerAnalysisCard
            key={t.ticker}
            ticker={t}
            expanded={expanded.has(t.ticker)}
            onToggle={() => toggleExpand(t.ticker)}
            onRefresh={refresh}
          />
        ))}

        <div style={{ height: "var(--nav-height)" }} />
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
