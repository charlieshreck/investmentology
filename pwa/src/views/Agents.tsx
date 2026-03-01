import { useEffect, useState } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { Skeleton } from "../components/shared/Skeleton";

interface LatestAnalysis {
  ticker: string;
  confidence: number | null;
  reasoning: string;
  createdAt: string;
}

interface AgentProfile {
  key: string;
  name: string;
  role: string;
  philosophy: string;
  focus: string;
  category: string;
  provider: string;
  model: string;
  online: boolean;
  totalSignals: number;
  avgConfidence: number | null;
  avgLatencyMs: number | null;
  lastActive: string | null;
  latestAnalysis: LatestAnalysis | null;
}

const categoryColor: Record<string, string> = {
  Fundamental: "var(--color-accent-bright)",
  Macro: "var(--color-warning)",
  Technical: "var(--color-success)",
  Risk: "var(--color-error)",
};

function AgentCard({ agent, expanded, onToggle }: { agent: AgentProfile; expanded: boolean; onToggle: () => void }) {
  const isAuditor = agent.key === "auditor";
  const borderColor = categoryColor[agent.category] ?? "var(--color-accent)";

  return (
    <div
      style={{
        background: "var(--color-surface-1)",
        border: isAuditor ? `2px solid ${borderColor}` : "1px solid var(--glass-border)",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
        transition: "border-color var(--duration-fast) var(--ease-out)",
      }}
    >
      {/* Header — always visible */}
      <button
        onClick={onToggle}
        style={{
          width: "100%",
          padding: "var(--space-lg)",
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          color: "var(--color-text)",
          fontFamily: "var(--font-sans)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: "var(--space-xs)" }}>
              <span style={{ fontSize: "var(--text-base)", fontWeight: 700 }}>
                {agent.name}
              </span>
              {isAuditor && <Badge variant="error">Devil's Advocate</Badge>}
              <Badge variant={agent.online ? "success" : "error"}>
                {agent.online ? "Online" : "Offline"}
              </Badge>
            </div>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
              {agent.role}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-xs)" }}>
              {agent.provider} &middot; {agent.model}
            </div>
          </div>
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: "var(--space-xs)",
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: "var(--radius-full)",
              background: borderColor,
              boxShadow: `0 0 8px ${borderColor}`,
            }} />
            {agent.avgConfidence != null && (
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 600 }}>
                {(agent.avgConfidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>

        {/* Stats row */}
        <div style={{
          display: "flex",
          gap: "var(--space-lg)",
          marginTop: "var(--space-md)",
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
        }}>
          <span>{agent.totalSignals} analyses</span>
          {agent.avgLatencyMs != null && <span>{(agent.avgLatencyMs / 1000).toFixed(1)}s avg</span>}
          {agent.lastActive && (
            <span>Last: {new Date(agent.lastActive).toLocaleDateString()}</span>
          )}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div style={{
          padding: "0 var(--space-lg) var(--space-lg)",
          borderTop: "1px solid var(--glass-border)",
        }}>
          {/* Philosophy & Focus */}
          <div style={{ paddingTop: "var(--space-md)" }}>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>
              Philosophy
            </div>
            <div style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
              {agent.philosophy}
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-md)", marginBottom: "var(--space-xs)" }}>
              Focus Areas
            </div>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
              {agent.focus}
            </div>
          </div>

          {/* Latest Analysis */}
          {agent.latestAnalysis && (
            <div style={{
              marginTop: "var(--space-lg)",
              padding: "var(--space-md)",
              background: "var(--color-surface-0)",
              borderRadius: "var(--radius-sm)",
              borderLeft: `3px solid ${borderColor}`,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-sm)" }}>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: "var(--text-sm)" }}>
                  {agent.latestAnalysis.ticker}
                </span>
                {agent.latestAnalysis.confidence != null && (
                  <Badge variant={
                    agent.latestAnalysis.confidence >= 0.7 ? "success" :
                    agent.latestAnalysis.confidence >= 0.4 ? "warning" : "error"
                  }>
                    {(agent.latestAnalysis.confidence * 100).toFixed(0)}%
                  </Badge>
                )}
              </div>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                {agent.latestAnalysis.reasoning}
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-sm)" }}>
                {new Date(agent.latestAnalysis.createdAt).toLocaleString()}
              </div>
            </div>
          )}

          {!agent.latestAnalysis && (
            <div style={{
              marginTop: "var(--space-lg)",
              padding: "var(--space-lg)",
              background: "var(--color-surface-0)",
              borderRadius: "var(--radius-sm)",
              textAlign: "center",
              fontSize: "var(--text-sm)",
              color: "var(--color-text-muted)",
            }}>
              No analyses yet. Run the pipeline to see this agent's opinion.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function Agents() {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>("auditor");
  const [tickerInput, setTickerInput] = useState("");
  const [activeTicker, setActiveTicker] = useState<string | null>(null);

  const loadAgents = async (ticker?: string) => {
    try {
      setLoading(true);
      const url = ticker
        ? `/api/invest/agents/panel?ticker=${encodeURIComponent(ticker)}`
        : "/api/invest/agents/panel";
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAgents(data.agents);
      setActiveTicker(ticker || null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, []);

  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Agents" subtitle="Multi-agent analysis panel" />
        <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          <Skeleton height={80} />
          <Skeleton height={80} />
          <Skeleton height={80} />
          <Skeleton height={80} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Agents" subtitle="Multi-agent analysis panel" />
        <div style={{ padding: "var(--space-xl)" }}>
          <BentoCard>
            <p style={{ color: "var(--color-error)" }}>{error}</p>
          </BentoCard>
        </div>
      </div>
    );
  }

  const online = agents.filter((a) => a.online).length;
  const auditor = agents.find((a) => a.key === "auditor");

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Agents"
        subtitle="Multi-agent analysis panel"
        right={
          <Badge variant={online === agents.length ? "success" : "warning"}>
            {online}/{agents.length} online
          </Badge>
        }
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
        {/* Ticker search */}
        <BentoCard>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const t = tickerInput.trim().toUpperCase();
              if (t) loadAgents(t);
            }}
            style={{ display: "flex", gap: "var(--space-md)", alignItems: "center" }}
          >
            <input
              type="text"
              placeholder="Enter ticker to view agent opinions..."
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              style={{
                flex: 1,
                padding: "var(--space-sm) var(--space-md)",
                background: "var(--color-surface-0)",
                border: "1px solid var(--glass-border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--color-text-primary)",
                fontFamily: "var(--font-mono)",
                fontSize: "var(--text-sm)",
              }}
            />
            <button
              type="submit"
              disabled={!tickerInput.trim()}
              style={{
                padding: "var(--space-sm) var(--space-lg)",
                background: tickerInput.trim() ? "var(--gradient-active)" : "var(--color-surface-2)",
                border: "none",
                borderRadius: "var(--radius-sm)",
                color: tickerInput.trim() ? "#fff" : "var(--color-text-muted)",
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                cursor: tickerInput.trim() ? "pointer" : "not-allowed",
              }}
            >
              Look Up
            </button>
            {activeTicker && (
              <button
                type="button"
                onClick={() => { setTickerInput(""); loadAgents(); }}
                style={{
                  padding: "var(--space-sm) var(--space-md)",
                  background: "var(--color-surface-0)",
                  border: "1px solid var(--glass-border)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--color-text-secondary)",
                  fontSize: "var(--text-xs)",
                  cursor: "pointer",
                }}
              >
                Clear
              </button>
            )}
          </form>
          {activeTicker && (
            <div style={{ marginTop: "var(--space-sm)", fontSize: "var(--text-xs)", color: "var(--color-accent-bright)" }}>
              Showing agent opinions for <strong>{activeTicker}</strong>
            </div>
          )}
        </BentoCard>

        {/* Auditor callout when it has an opinion */}
        {auditor?.latestAnalysis && (
          <BentoCard title="Auditor's Verdict">
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              marginBottom: "var(--space-md)",
            }}>
              <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "var(--text-base)" }}>
                {auditor.latestAnalysis.ticker}
              </span>
              {auditor.latestAnalysis.confidence != null && (
                <Badge variant={
                  auditor.latestAnalysis.confidence >= 0.7 ? "success" :
                  auditor.latestAnalysis.confidence >= 0.4 ? "warning" : "error"
                }>
                  Risk Confidence: {(auditor.latestAnalysis.confidence * 100).toFixed(0)}%
                </Badge>
              )}
            </div>
            <div style={{
              fontSize: "var(--text-sm)",
              color: "var(--color-text-secondary)",
              lineHeight: 1.6,
              borderLeft: "3px solid var(--color-error)",
              paddingLeft: "var(--space-md)",
            }}>
              {auditor.latestAnalysis.reasoning}
            </div>
          </BentoCard>
        )}

        {/* Agent cards — auditor first */}
        {[...agents].sort((a, b) => {
          if (a.key === "auditor") return -1;
          if (b.key === "auditor") return 1;
          return 0;
        }).map((agent) => (
          <AgentCard
            key={agent.key}
            agent={agent}
            expanded={expandedKey === agent.key}
            onToggle={() => setExpandedKey(expandedKey === agent.key ? null : agent.key)}
          />
        ))}

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}
