/**
 * PortfolioHealthStrip — 3-tier information density for portfolio allocation.
 *
 * Tier 1 (Glance): Compact strip with colored allocation dots + regime badge + gap summary
 * Tier 2 (Explore): Expandable panel with risk allocation bars + sector breakdown + warnings
 * Tier 3 (Deep): Entry criteria + full allocation guidance (revealed on second expand)
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, AlertTriangle, TrendingUp, Shield, Zap, BarChart3 } from "lucide-react";
import type { PortfolioGaps, AllocationGuidance } from "../../types/api";

// Risk category display config
const RISK_META: Record<string, { label: string; color: string; icon: typeof TrendingUp }> = {
  growth:    { label: "Growth",    color: "#22d3ee", icon: TrendingUp },
  cyclical:  { label: "Cyclical",  color: "#fbbf24", icon: BarChart3 },
  defensive: { label: "Defensive", color: "#34d399", icon: Shield },
  mixed:     { label: "Mixed",     color: "#a78bfa", icon: Zap },
  income:    { label: "Income",    color: "#f472b6", icon: BarChart3 },
};

const STANCE_META: Record<string, { label: string; color: string; bg: string }> = {
  aggressive: { label: "Aggressive", color: "#22d3ee", bg: "rgba(34,211,238,0.12)" },
  standard:   { label: "Standard",   color: "#34d399", bg: "rgba(52,211,153,0.12)" },
  cautious:   { label: "Cautious",   color: "#fbbf24", bg: "rgba(251,191,36,0.12)" },
  defensive:  { label: "Defensive",  color: "#f87171", bg: "rgba(248,113,113,0.12)" },
};

const STATUS_DOT: Record<string, string> = {
  underweight: "#f87171",
  slightly_underweight: "#fbbf24",
  balanced: "#34d399",
  slightly_overweight: "#fbbf24",
  overweight: "#f87171",
  empty: "var(--color-text-muted)",
};

export function PortfolioHealthStrip({
  gaps,
  guidance,
}: {
  gaps?: PortfolioGaps;
  guidance?: AllocationGuidance;
}) {
  const [tier, setTier] = useState<1 | 2 | 3>(1);

  if (!gaps && !guidance) return null;

  const categories = Object.keys(RISK_META);
  const underweight = gaps?.underweightCategories ?? [];
  const overweight = gaps?.overweightCategories ?? [];
  const warnings = gaps?.concentrationWarnings ?? [];
  const hasIssues = underweight.length > 0 || overweight.length > 0 || warnings.length > 0;
  const stanceMeta = guidance ? STANCE_META[guidance.stance] ?? STANCE_META.standard : null;

  // Build summary text for Tier 1
  let summaryText = "Portfolio balanced";
  if (gaps?.positionCount === 0) {
    summaryText = "No positions yet";
  } else if (underweight.length > 0) {
    const labels = underweight.map(c => RISK_META[c]?.label ?? c);
    summaryText = `Needs: ${labels.join(", ")}`;
  } else if (overweight.length > 0) {
    const labels = overweight.map(c => RISK_META[c]?.label ?? c);
    summaryText = `Heavy: ${labels.join(", ")}`;
  }

  const handleClick = () => {
    setTier(t => t === 1 ? 2 : t === 2 ? 3 : 1);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        borderRadius: "var(--radius-lg)",
        background: "var(--color-surface-0)",
        border: `1px solid ${hasIssues ? "rgba(251,191,36,0.15)" : "var(--glass-border)"}`,
        overflow: "hidden",
      }}
    >
      {/* ── Tier 1: Glance Strip ── */}
      <div
        onClick={handleClick}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        {/* Allocation dots */}
        <div style={{ display: "flex", gap: 3, flexShrink: 0 }}>
          {categories.map(cat => {
            const alloc = gaps?.riskAllocations?.[cat];
            const dotColor = alloc ? STATUS_DOT[alloc.status] ?? "var(--color-text-muted)" : "var(--color-surface-2)";
            return (
              <div
                key={cat}
                title={`${RISK_META[cat].label}: ${alloc?.current_pct ?? 0}% (ideal ${alloc?.ideal_pct ?? "?"}%)`}
                style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: dotColor,
                  transition: "background 0.3s ease",
                }}
              />
            );
          })}
        </div>

        {/* Regime badge */}
        {stanceMeta && (
          <span style={{
            fontSize: 9, fontWeight: 700,
            padding: "2px 8px", borderRadius: 99,
            background: stanceMeta.bg,
            color: stanceMeta.color,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            flexShrink: 0,
          }}>
            {stanceMeta.label}
          </span>
        )}

        {/* Summary text */}
        <span style={{
          flex: 1,
          fontSize: 11,
          fontWeight: 600,
          color: hasIssues ? "var(--color-warning)" : "var(--color-text-secondary)",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}>
          {summaryText}
        </span>

        {/* Position count */}
        {gaps && gaps.positionCount > 0 && (
          <span style={{
            fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
            color: "var(--color-text-muted)", flexShrink: 0,
          }}>
            {gaps.positionCount} pos
          </span>
        )}

        {/* Expand indicator */}
        <motion.div
          animate={{ rotate: tier > 1 ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown size={14} color="var(--color-text-muted)" />
        </motion.div>
      </div>

      {/* ── Tier 2: Explore Panel ── */}
      <AnimatePresence>
        {tier >= 2 && gaps && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div style={{
              padding: "0 14px 14px",
              borderTop: "1px solid var(--glass-border)",
            }}>
              {/* Risk allocation bars */}
              <div style={{ marginTop: 12 }}>
                <div style={{
                  fontSize: 9, fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.06em", color: "var(--color-text-muted)",
                  marginBottom: 8,
                }}>
                  Risk Balance
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {categories.map(cat => {
                    const meta = RISK_META[cat];
                    const alloc = gaps.riskAllocations?.[cat];
                    if (!alloc) return null;
                    const currentPct = alloc.current_pct;
                    const idealPct = alloc.ideal_pct;
                    const isUnder = underweight.includes(cat);
                    const isOver = overweight.includes(cat);

                    return (
                      <div key={cat}>
                        <div style={{
                          display: "flex", justifyContent: "space-between",
                          marginBottom: 2,
                        }}>
                          <span style={{
                            fontSize: 10, fontWeight: 600,
                            color: isUnder ? "var(--color-error)" : isOver ? "var(--color-warning)" : "var(--color-text-secondary)",
                          }}>
                            {meta.label}
                            {isUnder && <span style={{ fontSize: 9, opacity: 0.8 }}> — needs more</span>}
                            {isOver && <span style={{ fontSize: 9, opacity: 0.8 }}> — overweight</span>}
                          </span>
                          <span style={{
                            fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
                            color: "var(--color-text-muted)",
                          }}>
                            {currentPct}% / {idealPct}%
                          </span>
                        </div>

                        {/* Bar */}
                        <div style={{
                          position: "relative", height: 6,
                          background: "var(--color-surface-2)",
                          borderRadius: 3, overflow: "hidden",
                        }}>
                          {/* Current allocation */}
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(currentPct, 100)}%` }}
                            transition={{ duration: 0.6, ease: "easeOut" }}
                            style={{
                              height: "100%",
                              background: meta.color,
                              borderRadius: 3,
                              opacity: 0.8,
                            }}
                          />
                          {/* Ideal marker */}
                          <div style={{
                            position: "absolute",
                            left: `${idealPct}%`,
                            top: -1, bottom: -1,
                            width: 2,
                            background: "var(--color-text)",
                            opacity: 0.3,
                            borderRadius: 1,
                          }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Sector breakdown - compact */}
              {gaps.sectorAllocations && Object.keys(gaps.sectorAllocations).length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{
                    fontSize: 9, fontWeight: 700, textTransform: "uppercase",
                    letterSpacing: "0.06em", color: "var(--color-text-muted)",
                    marginBottom: 6,
                  }}>
                    Sectors
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                    {Object.entries(gaps.sectorAllocations)
                      .sort(([, a], [, b]) => b - a)
                      .map(([sector, pct]) => (
                        <span key={sector} style={{
                          fontSize: 9, fontWeight: 600,
                          padding: "2px 7px", borderRadius: 99,
                          background: pct > 40
                            ? "rgba(248,113,113,0.12)"
                            : pct > 25
                              ? "rgba(251,191,36,0.08)"
                              : "rgba(148,163,184,0.08)",
                          color: pct > 40
                            ? "var(--color-error)"
                            : "var(--color-text-secondary)",
                          whiteSpace: "nowrap",
                        }}>
                          {sector} {pct}%
                        </span>
                      ))}
                  </div>
                </div>
              )}

              {/* Concentration warnings */}
              {warnings.length > 0 && (
                <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
                  {warnings.map((w, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 6,
                      fontSize: 10, color: "var(--color-warning)",
                    }}>
                      <AlertTriangle size={11} />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Tier 3: Deep Dive ── */}
      <AnimatePresence>
        {tier >= 3 && guidance && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div style={{
              padding: "0 14px 14px",
              borderTop: "1px solid var(--glass-border)",
            }}>
              {/* Allocation targets */}
              <div style={{ marginTop: 12 }}>
                <div style={{
                  fontSize: 9, fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.06em", color: "var(--color-text-muted)",
                  marginBottom: 8,
                }}>
                  Macro Regime Guidance
                </div>

                {/* Equity/Cash target bars */}
                <div style={{
                  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8,
                  marginBottom: 10,
                }}>
                  <div style={{
                    padding: "8px 10px",
                    background: "rgba(52,211,153,0.06)",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid rgba(52,211,153,0.1)",
                  }}>
                    <div style={{
                      fontSize: 8, fontWeight: 700, textTransform: "uppercase",
                      letterSpacing: "0.06em", color: "var(--color-text-muted)",
                      marginBottom: 4,
                    }}>
                      Equity Target
                    </div>
                    <div style={{
                      fontSize: 16, fontWeight: 800, fontFamily: "var(--font-mono)",
                      color: "var(--color-success)",
                    }}>
                      {guidance.equityTargetMin}–{guidance.equityTargetMax}%
                    </div>
                  </div>
                  <div style={{
                    padding: "8px 10px",
                    background: "rgba(148,163,184,0.06)",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid rgba(148,163,184,0.1)",
                  }}>
                    <div style={{
                      fontSize: 8, fontWeight: 700, textTransform: "uppercase",
                      letterSpacing: "0.06em", color: "var(--color-text-muted)",
                      marginBottom: 4,
                    }}>
                      Cash Target
                    </div>
                    <div style={{
                      fontSize: 16, fontWeight: 800, fontFamily: "var(--font-mono)",
                      color: "var(--color-text-secondary)",
                    }}>
                      {guidance.cashTargetMin}–{guidance.cashTargetMax}%
                    </div>
                  </div>
                </div>

                {/* Entry criteria */}
                <div style={{
                  padding: "8px 10px",
                  background: "var(--color-surface-1)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--glass-border)",
                }}>
                  <div style={{
                    fontSize: 8, fontWeight: 700, textTransform: "uppercase",
                    letterSpacing: "0.06em", color: "var(--color-text-muted)",
                    marginBottom: 4,
                  }}>
                    Entry Criteria
                  </div>
                  <div style={{
                    fontSize: 11, lineHeight: 1.5, color: "var(--color-text-secondary)",
                  }}>
                    {guidance.entryCriteria}
                  </div>
                </div>

                {/* Full summary */}
                <div style={{
                  marginTop: 8,
                  fontSize: 10, lineHeight: 1.5, color: "var(--color-text-muted)",
                  fontStyle: "italic",
                }}>
                  {guidance.summary}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/**
 * Sector-to-risk-category mapping (mirrors backend SECTOR_RISK_MAP).
 * Exported so RecCard can check if a recommendation fills a gap.
 */
export const SECTOR_RISK_MAP: Record<string, string> = {
  "Technology": "growth",
  "Communication Services": "growth",
  "Consumer Cyclical": "growth",
  "Consumer Defensive": "defensive",
  "Utilities": "defensive",
  "Healthcare": "mixed",
  "Financial Services": "cyclical",
  "Industrials": "cyclical",
  "Basic Materials": "cyclical",
  "Energy": "cyclical",
  "Real Estate": "income",
};
