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

interface SignalEntry {
  signal: string;
  count: number;
  agents: string[];
}

/**
 * Frequency-weighted signal pill cloud from all agents' key_signals.
 * Multi-agent signals get a count badge and stronger colour.
 * Signals from a single agent get an outline style.
 */
export function SignalTagCloud({ stances }: { stances: AgentStance[] }) {
  const valid = stances.filter(
    (s) => s.summary && s.summary !== "Failed to parse LLM response"
  );
  if (!valid.length) return null;

  // Collect and deduplicate signals
  const signalMap = new Map<string, { count: number; agents: string[] }>();
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
        signalMap.set(key, { count: 1, agents: [stance.name.toLowerCase()] });
      }
    }
  }

  // Sort by frequency (descending), then alphabetically
  const signals: SignalEntry[] = Array.from(signalMap.entries())
    .map(([signal, { count, agents }]) => ({ signal, count, agents }))
    .sort((a, b) => b.count - a.count || a.signal.localeCompare(b.signal));

  if (!signals.length) return null;

  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {signals.slice(0, 12).map((entry) => {
        const isMulti = entry.count > 1;
        // Use first agent's colour for single-agent signals, accent for multi
        const agentCol = entry.agents.length === 1
          ? AGENT_COLORS[entry.agents[0]] ?? "var(--color-text-muted)"
          : "var(--color-accent-bright)";

        return (
          <span
            key={entry.signal}
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
              ...(isMulti
                ? {
                    background: `${agentCol}18`,
                    color: agentCol,
                    border: `1px solid ${agentCol}30`,
                  }
                : {
                    background: "transparent",
                    color: `${agentCol}cc`,
                    border: `1px solid ${agentCol}25`,
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
  );
}
