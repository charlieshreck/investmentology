import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { AgentStance } from "../../types/models";

// Signature colours per agent
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

const AGENT_INITIALS: Record<string, string> = {
  warren: "WB",
  auditor: "RA",
  klarman: "SK",
  soros: "GS",
  druckenmiller: "SD",
  dalio: "RD",
  simons: "JS",
  lynch: "PL",
  data_analyst: "DA",
};

function sentimentColor(s: number): string {
  if (s >= 0.5) return "var(--color-success)";
  if (s >= 0.15) return "rgba(52, 211, 153, 0.6)";
  if (s > -0.15) return "var(--color-warning)";
  if (s > -0.5) return "rgba(248, 113, 113, 0.6)";
  return "var(--color-error)";
}

function stanceWord(s: number): string {
  if (s >= 0.5) return "Bullish";
  if (s >= 0.15) return "Lean Bull";
  if (s > -0.15) return "Neutral";
  if (s > -0.5) return "Lean Bear";
  return "Bearish";
}

/**
 * Visual consensus display: consensus ring + agent avatar tiles.
 * Replaces text-heavy agent accordion with scannable visual layout.
 */
export function AgentConsensusPanel({ stances, consensusScore }: {
  stances: AgentStance[];
  consensusScore: number | null;
}) {
  const [activeAgent, setActiveAgent] = useState<string | null>(null);

  if (!stances.length) return null;

  // Consensus ring value: consensusScore is -1 to +1, map to 0-100
  const ringPct = consensusScore != null
    ? Math.round(((consensusScore + 1) / 2) * 100)
    : Math.round(
      (stances.filter((s) => s.sentiment >= 0.15).length / stances.length) * 100
    );

  const ringColor =
    ringPct >= 75 ? "var(--color-success)" :
    ringPct >= 50 ? "var(--color-warning)" :
    "var(--color-error)";

  const size = 56;
  const stroke = 5;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - ringPct / 100);

  const activeStance = stances.find(
    (s) => s.name.toLowerCase() === activeAgent
  );

  return (
    <div>
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-lg)",
      }}>
        {/* Consensus Ring */}
        <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
          <svg width={size} height={size}>
            <circle
              cx={size / 2} cy={size / 2} r={radius}
              fill="none" stroke="var(--color-surface-2)" strokeWidth={stroke}
            />
            <motion.circle
              cx={size / 2} cy={size / 2} r={radius}
              fill="none" stroke={ringColor} strokeWidth={stroke}
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: offset }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              strokeLinecap="round"
            />
          </svg>
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
          }}>
            <span style={{
              fontSize: 14, fontWeight: 800,
              fontFamily: "var(--font-mono)",
              color: ringColor, lineHeight: 1,
            }}>
              {ringPct}%
            </span>
          </div>
        </div>

        {/* Agent Avatar Row */}
        <div style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          flex: 1,
        }}>
          {stances
            .filter((s) => s.summary && s.summary !== "Failed to parse LLM response")
            .map((stance) => {
              const key = stance.name.toLowerCase();
              const agentCol = AGENT_COLORS[key] ?? "var(--color-text-muted)";
              const initials = AGENT_INITIALS[key] ?? stance.name.charAt(0).toUpperCase();
              const sentCol = sentimentColor(stance.sentiment);
              const isActive = activeAgent === key;

              return (
                <motion.button
                  key={key}
                  onClick={() => setActiveAgent(isActive ? null : key)}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: `${sentCol}20`,
                    border: isActive
                      ? `2px solid ${agentCol}`
                      : `2px solid ${sentCol}40`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    padding: 0,
                    flexShrink: 0,
                    transition: "border-color 0.15s ease",
                  }}
                  title={`${stance.name}: ${stanceWord(stance.sentiment)} (${(stance.confidence * 100).toFixed(0)}%)`}
                >
                  <span style={{
                    fontSize: 10,
                    fontWeight: 800,
                    color: agentCol,
                    lineHeight: 1,
                  }}>
                    {initials}
                  </span>
                </motion.button>
              );
            })}
        </div>
      </div>

      {/* Active agent tooltip */}
      <AnimatePresence>
        {activeStance && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            style={{ overflow: "hidden" }}
          >
            <div style={{
              marginTop: "var(--space-sm)",
              padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-surface-0)",
              borderRadius: "var(--radius-md)",
              border: `1px solid ${AGENT_COLORS[activeAgent!] ?? "var(--glass-border)"}30`,
            }}>
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: 4,
              }}>
                <span style={{
                  fontSize: 11, fontWeight: 700,
                  color: AGENT_COLORS[activeAgent!] ?? "var(--color-text)",
                  textTransform: "capitalize",
                }}>
                  {activeStance.name}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 600,
                  color: sentimentColor(activeStance.sentiment),
                }}>
                  {stanceWord(activeStance.sentiment)}
                </span>
                <span style={{
                  fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 700,
                  color: "var(--color-text-muted)", marginLeft: "auto",
                }}>
                  {(activeStance.confidence * 100).toFixed(0)}% conf
                </span>
              </div>
              <div style={{
                fontSize: 11, color: "var(--color-text-secondary)",
                lineHeight: 1.4,
              }}>
                {activeStance.summary}
              </div>
              {activeStance.key_signals.length > 0 && (
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
                  {activeStance.key_signals.slice(0, 4).map((s, i) => (
                    <span key={i} style={{
                      fontSize: 9, padding: "1px 6px", borderRadius: 4,
                      background: `${AGENT_COLORS[activeAgent!] ?? "var(--color-text-muted)"}15`,
                      color: AGENT_COLORS[activeAgent!] ?? "var(--color-text-muted)",
                      fontWeight: 600,
                      border: `1px solid ${AGENT_COLORS[activeAgent!] ?? "var(--color-text-muted)"}20`,
                    }}>
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
