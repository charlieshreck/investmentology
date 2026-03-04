import { useState } from "react";
import type { AgentStance } from "../../types/models";

// Signature colours per agent (same as AgentConsensusPanel)
const AGENT_COLORS: Record<string, string> = {
  warren: "#34d399",
  auditor: "#fbbf24",
  klarman: "#60a5fa",
  soros: "#f472b6",
  druckenmiller: "#c084fc",
  dalio: "#fb923c",
  simons: "#a78bfa",
  lynch: "#38bdf8",
  data_analyst: "#94a3b8",
};

interface SignalDetail {
  agent: string;
  detail: string;
}

interface SignalEntry {
  signal: string;
  count: number;
  agents: string[];
  details: SignalDetail[];
}

/**
 * Frequency-weighted signal pill cloud from all agents' key_signals.
 * Multi-agent signals get a count badge and stronger colour.
 * Signals from a single agent get an outline style.
 * Click any tag to see the detail prose from the agent(s) who emitted it.
 */
export function SignalTagCloud({ stances, signalData }: {
  stances: AgentStance[];
  signalData?: { agentName: string; signals: { signals?: { tag?: string; detail?: string; strength?: string }[] } | null }[];
}) {
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const valid = stances.filter(
    (s) => s.summary && s.summary !== "Failed to parse LLM response"
  );
  if (!valid.length) return null;

  // Build a lookup of signal details from full signal data
  const detailLookup = new Map<string, SignalDetail[]>();
  if (signalData) {
    for (const sd of signalData) {
      const sigs = sd.signals?.signals;
      if (!Array.isArray(sigs)) continue;
      for (const sig of sigs) {
        if (!sig.tag || !sig.detail) continue;
        const key = sig.tag.toLowerCase().trim();
        const existing = detailLookup.get(key) ?? [];
        existing.push({ agent: sd.agentName, detail: sig.detail });
        detailLookup.set(key, existing);
      }
    }
  }

  // Collect and deduplicate signals
  const signalMap = new Map<string, { count: number; agents: string[]; details: SignalDetail[] }>();
  for (const stance of valid) {
    for (const sig of stance.key_signals) {
      const key = sig.toLowerCase().trim();
      const existing = signalMap.get(key);
      if (existing) {
        existing.count++;
        if (!existing.agents.includes(stance.name.toLowerCase())) {
          existing.agents.push(stance.name.toLowerCase());
        }
      } else {
        signalMap.set(key, {
          count: 1,
          agents: [stance.name.toLowerCase()],
          details: detailLookup.get(key) ?? [],
        });
      }
    }
  }

  // Sort by frequency (descending), then alphabetically
  const signals: SignalEntry[] = Array.from(signalMap.entries())
    .map(([signal, { count, agents, details }]) => ({ signal, count, agents, details }))
    .sort((a, b) => b.count - a.count || a.signal.localeCompare(b.signal));

  if (!signals.length) return null;

  const activeEntry = activeTag ? signals.find(s => s.signal === activeTag) : null;

  return (
    <div>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {signals.slice(0, 12).map((entry) => {
          const isMulti = entry.count > 1;
          const hasDetail = entry.details.length > 0;
          // Use first agent's colour for single-agent signals, accent for multi
          const agentCol = entry.agents.length === 1
            ? AGENT_COLORS[entry.agents[0]] ?? "var(--color-text-muted)"
            : "var(--color-accent-bright)";
          const isActive = activeTag === entry.signal;

          return (
            <span
              key={entry.signal}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTag(isActive ? null : entry.signal);
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 3,
                padding: "2px 7px",
                borderRadius: 4,
                fontSize: 9,
                fontWeight: 600,
                lineHeight: 1.4,
                whiteSpace: "nowrap",
                cursor: hasDetail ? "pointer" : "default",
                transition: "all 0.15s",
                ...(isMulti
                  ? {
                      background: isActive ? `${agentCol}30` : `${agentCol}18`,
                      color: agentCol,
                      border: `1px solid ${isActive ? agentCol : `${agentCol}30`}`,
                    }
                  : {
                      background: isActive ? `${agentCol}18` : "transparent",
                      color: `${agentCol}cc`,
                      border: `1px solid ${isActive ? agentCol : `${agentCol}25`}`,
                    }),
              }}
            >
              {entry.signal}
              {isMulti && (
                <span style={{
                  fontSize: 8,
                  fontWeight: 800,
                  opacity: 0.8,
                  fontFamily: "var(--font-mono)",
                }}>
                  {"\u00D7"}{entry.count}
                </span>
              )}
            </span>
          );
        })}
      </div>

      {/* Detail popover */}
      {activeEntry && activeEntry.details.length > 0 && (
        <div style={{
          marginTop: "var(--space-sm)",
          padding: "var(--space-sm) var(--space-md)",
          background: "var(--color-surface-0)",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--glass-border)",
        }}>
          {activeEntry.details.map((d, i) => (
            <div key={i} style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-text-secondary)",
              lineHeight: 1.5,
              marginBottom: i < activeEntry.details.length - 1 ? "var(--space-xs)" : 0,
              paddingBottom: i < activeEntry.details.length - 1 ? "var(--space-xs)" : 0,
              borderBottom: i < activeEntry.details.length - 1 ? "1px solid var(--glass-border)" : "none",
            }}>
              <span style={{
                fontWeight: 700,
                color: AGENT_COLORS[d.agent.toLowerCase()] ?? "var(--color-text-muted)",
                textTransform: "capitalize",
                marginRight: "var(--space-xs)",
              }}>
                {d.agent}:
              </span>
              {d.detail}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
