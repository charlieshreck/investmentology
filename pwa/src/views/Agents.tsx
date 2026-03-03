import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { Skeleton } from "../components/shared/Skeleton";
import { ChevronDown } from "lucide-react";

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
  critical_rules?: string[];
  allowed_tags?: string[];
}

const categoryColor: Record<string, string> = {
  Primary: "var(--color-accent-bright)",
  Screener: "var(--color-warning)",
  Scout: "var(--color-success)",
  Synthesis: "var(--color-warning)",
  Fundamental: "var(--color-accent-bright)",
  Macro: "var(--color-warning)",
  Technical: "var(--color-success)",
  Risk: "var(--color-error)",
};

const categoryDescriptions: Record<string, string> = {
  Primary: "The main analysts — each examines stocks through a different investment philosophy",
  Screener: "Quick-check experts — they decide if a stock is worth the full team's time",
  Scout: "Fast, cost-effective analysts that provide supporting opinions",
  Synthesis: "Combines all agent opinions into a final recommendation",
};

const categoryOrder = ["Primary", "Screener", "Scout", "Synthesis"];

/** Classify allowed_tags into signal categories for the fingerprint bar. */
const TAG_CATEGORIES: Record<string, { label: string; color: string }> = {
  fundamental: { label: "Fund", color: "var(--color-accent-bright)" },
  macro: { label: "Macro", color: "var(--color-warning)" },
  technical: { label: "Tech", color: "var(--color-success)" },
  risk: { label: "Risk", color: "var(--color-error)" },
  action: { label: "Act", color: "var(--color-text-secondary)" },
};

function classifyTag(tag: string): string {
  const t = tag.toLowerCase();
  if (t.includes("macro") || t.includes("cycle") || t.includes("geopolitical") || t.includes("monetary") || t.includes("fiscal") || t.includes("credit")) return "macro";
  if (t.includes("technical") || t.includes("momentum") || t.includes("trend") || t.includes("rsi") || t.includes("macd") || t.includes("volume") || t.includes("support") || t.includes("resistance")) return "technical";
  if (t.includes("risk") || t.includes("leverage") || t.includes("volatility") || t.includes("concentration") || t.includes("governance") || t.includes("liquidity")) return "risk";
  if (t.includes("action") || t.includes("buy") || t.includes("sell") || t.includes("trim") || t.includes("hold") || t.includes("no_action")) return "action";
  return "fundamental";
}

function SignalFingerprint({ tags }: { tags: string[] }) {
  if (!tags || tags.length === 0) return null;

  const counts: Record<string, number> = {};
  for (const tag of tags) {
    const cat = classifyTag(tag);
    counts[cat] = (counts[cat] || 0) + 1;
  }
  const total = tags.length;

  return (
    <div style={{ display: "flex", gap: 2, height: 6, borderRadius: 3, overflow: "hidden", width: "100%" }}>
      {Object.entries(TAG_CATEGORIES).map(([key, { color }]) => {
        const pct = ((counts[key] || 0) / total) * 100;
        if (pct === 0) return null;
        return (
          <div
            key={key}
            title={`${TAG_CATEGORIES[key].label}: ${counts[key]} tags`}
            style={{
              flex: pct,
              background: color,
              borderRadius: 1,
              minWidth: pct > 0 ? 3 : 0,
            }}
          />
        );
      })}
    </div>
  );
}

function MantraChips({ rules }: { rules: string[] }) {
  if (!rules || rules.length === 0) return null;

  // Extract short phrases from rules (first sentence or first ~60 chars)
  const chips = rules.slice(0, 4).map((rule) => {
    const short = rule.split(".")[0].replace(/^(Use ONLY|ALWAYS|NEVER|If |Be |No |Focus )/i, "").trim();
    return short.length > 50 ? short.slice(0, 47) + "..." : short;
  });

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-xs)" }}>
      {chips.map((chip, i) => (
        <span
          key={i}
          style={{
            padding: "2px var(--space-sm)",
            fontSize: 10,
            fontWeight: 500,
            color: "var(--color-text-secondary)",
            background: "var(--color-surface-0)",
            border: "1px solid var(--glass-border)",
            borderRadius: "var(--radius-full)",
            whiteSpace: "nowrap",
            maxWidth: 200,
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {chip}
        </span>
      ))}
    </div>
  );
}

function ConfidenceRing({ value, size = 28 }: { value: number; size?: number }) {
  const r = (size - 4) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value));
  const color = pct >= 0.7 ? "var(--color-success)" : pct >= 0.4 ? "var(--color-warning)" : "var(--color-error)";

  return (
    <svg width={size} height={size} style={{ flexShrink: 0 }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-surface-2)" strokeWidth={3} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={3}
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - pct)}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x={size / 2} y={size / 2 + 1} textAnchor="middle" dominantBaseline="central"
        style={{ fontSize: 8, fill: "var(--color-text-secondary)", fontFamily: "var(--font-mono)", fontWeight: 700 }}>
        {Math.round(pct * 100)}
      </text>
    </svg>
  );
}

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
          padding: "var(--space-md) var(--space-lg)",
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
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: 2 }}>
              <span style={{ fontSize: "var(--text-base)", fontWeight: 700 }}>
                {agent.name}
              </span>
              {isAuditor && <Badge variant="error">Devil's Advocate</Badge>}
              <div style={{
                width: 6, height: 6, borderRadius: "var(--radius-full)",
                background: agent.online ? "var(--color-success)" : "var(--color-error)",
              }} />
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {agent.provider} &middot; {agent.model}
              {agent.totalSignals > 0 && <> &middot; {agent.totalSignals} analyses</>}
              {agent.avgLatencyMs != null && <> &middot; {(agent.avgLatencyMs / 1000).toFixed(1)}s</>}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
            {agent.avgConfidence != null && (
              <ConfidenceRing value={agent.avgConfidence} />
            )}
            <motion.div
              animate={{ rotate: expanded ? 180 : 0 }}
              transition={{ duration: 0.2 }}
              style={{ color: "var(--color-text-muted)" }}
            >
              <ChevronDown size={14} />
            </motion.div>
          </div>
        </div>

        {/* Signal Fingerprint bar — always visible */}
        {agent.allowed_tags && agent.allowed_tags.length > 0 && (
          <div style={{ marginTop: "var(--space-sm)" }}>
            <SignalFingerprint tags={agent.allowed_tags} />
            <div style={{ display: "flex", gap: "var(--space-md)", marginTop: 3 }}>
              {Object.entries(TAG_CATEGORIES).map(([key, { label, color }]) => {
                const count = agent.allowed_tags!.filter((t) => classifyTag(t) === key).length;
                if (count === 0) return null;
                return (
                  <span key={key} style={{ fontSize: 9, color: "var(--color-text-muted)" }}>
                    <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: 2, background: color, marginRight: 3, verticalAlign: "middle" }} />
                    {label}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* Mantra chips — always visible */}
        {agent.critical_rules && agent.critical_rules.length > 0 && (
          <div style={{ marginTop: "var(--space-sm)" }}>
            <MantraChips rules={agent.critical_rules} />
          </div>
        )}

        {/* Latest analysis — compact, always visible if available */}
        {agent.latestAnalysis && (
          <div style={{
            marginTop: "var(--space-sm)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-sm)",
          }}>
            {agent.latestAnalysis.confidence != null && (
              <ConfidenceRing value={agent.latestAnalysis.confidence} size={24} />
            )}
            <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: "var(--text-xs)" }}>
              {agent.latestAnalysis.ticker}
            </span>
            <span style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
              flex: 1,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}>
              {agent.latestAnalysis.reasoning.split(".")[0]}
            </span>
          </div>
        )}
      </button>

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div style={{
              padding: "var(--space-md) var(--space-lg) var(--space-lg)",
              borderTop: "1px solid var(--glass-border)",
            }}>
              {/* Focus */}
              <div style={{
                fontSize: "var(--text-sm)",
                color: "var(--color-text-secondary)",
                lineHeight: 1.5,
                fontStyle: "italic",
                marginBottom: "var(--space-md)",
              }}>
                "{agent.focus}"
              </div>

              {/* Full critical rules */}
              {agent.critical_rules && agent.critical_rules.length > 0 && (
                <div style={{ marginBottom: "var(--space-md)" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Core Rules
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
                    {agent.critical_rules.map((rule, i) => (
                      <div key={i} style={{
                        fontSize: 11,
                        color: "var(--color-text-secondary)",
                        lineHeight: 1.4,
                        paddingLeft: "var(--space-md)",
                        borderLeft: `2px solid ${borderColor}`,
                      }}>
                        {rule}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Signal tag inventory */}
              {agent.allowed_tags && agent.allowed_tags.length > 0 && (
                <div style={{ marginBottom: "var(--space-md)" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Signal Vocabulary ({agent.allowed_tags.length} tags)
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                    {agent.allowed_tags.map((tag) => {
                      const cat = classifyTag(tag);
                      const color = TAG_CATEGORIES[cat]?.color ?? "var(--color-text-muted)";
                      return (
                        <span key={tag} style={{
                          padding: "1px var(--space-xs)",
                          fontSize: 9,
                          fontFamily: "var(--font-mono)",
                          color,
                          background: "var(--color-surface-0)",
                          border: `1px solid ${color}`,
                          borderRadius: "var(--radius-sm)",
                          opacity: 0.8,
                        }}>
                          {tag.replace(/_/g, " ")}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Full latest analysis */}
              {agent.latestAnalysis && (
                <div style={{
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
                  padding: "var(--space-md)",
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Agents() {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
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

        {/* Agent cards grouped by category */}
        {categoryOrder.map((cat) => {
          const catAgents = agents.filter((a) => a.category === cat);
          if (catAgents.length === 0) return null;
          const sorted = cat === "Primary"
            ? [...catAgents].sort((a, b) => a.key === "auditor" ? -1 : b.key === "auditor" ? 1 : 0)
            : catAgents;
          return (
            <div key={cat}>
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-sm)",
                marginTop: "var(--space-sm)",
              }}>
                <div style={{
                  width: 8,
                  height: 8,
                  borderRadius: "var(--radius-full)",
                  background: categoryColor[cat] ?? "var(--color-accent)",
                }} />
                <span style={{
                  fontSize: "var(--text-xs)",
                  fontWeight: 700,
                  color: "var(--color-text)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                }}>
                  {cat} ({sorted.length})
                </span>
                {categoryDescriptions[cat] && (
                  <span style={{
                    fontSize: 10,
                    color: "var(--color-text-muted)",
                  }}>
                    — {categoryDescriptions[cat]}
                  </span>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)", marginBottom: "var(--space-lg)" }}>
                {sorted.map((agent) => (
                  <AgentCard
                    key={agent.key}
                    agent={agent}
                    expanded={expandedKey === agent.key}
                    onToggle={() => setExpandedKey(expandedKey === agent.key ? null : agent.key)}
                  />
                ))}
              </div>
            </div>
          );
        })}
        {/* Ungrouped agents (legacy) */}
        {agents.filter((a) => !categoryOrder.includes(a.category)).map((agent) => (
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
