import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Sunrise, ChevronDown, ChevronRight, AlertTriangle, ArrowRight,
  TrendingUp, TrendingDown, Minus,
} from "lucide-react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { AnimatedNumber } from "../components/shared/AnimatedNumber";
import { useStore } from "../stores/useStore";
import { usePortfolio } from "../hooks/usePortfolio";
import { useDailyBriefing, usePortfolioAdvisor, useThesisSummary, useTopRecommendations } from "../hooks/useToday";
import type { AdvisorAction, ThesisPosition } from "../hooks/useToday";
import type { Alert } from "../types/models";
import { verdictLabel, verdictBadgeVariant } from "../utils/verdictHelpers";

// ═══════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════

const fmtCurrency = (n: number) =>
  "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

const fmtPnl = (n: number) =>
  (n >= 0 ? "+" : "") + "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

// Urgency order for sorting unified actions
const urgencyOrder: Record<string, number> = {
  SELL: 0, critical: 0, error: 1, TRIM: 2, warning: 2, REVIEW: 3, REBALANCE: 4, BUY: 5, ACCUMULATE: 6,
};

// Unified action item (from advisor actions + alerts)
interface PriorityItem {
  key: string;
  source: "action" | "alert";
  type: string;
  ticker: string | null;
  title: string;
  detail: string;
  urgency: number;
  badgeVariant: "error" | "warning" | "accent" | "success" | "neutral";
  borderColor: string;
  // Only for actions
  action?: AdvisorAction;
  // Only for alerts
  alert?: Alert;
}

// ═══════════════════════════════════════════════════════════════════
// Priority Action Row
// ═══════════════════════════════════════════════════════════════════

const actionColors: Record<string, { dot: string; badge: "error" | "warning" | "accent" | "success" | "neutral" }> = {
  SELL: { dot: "var(--color-error)", badge: "error" },
  TRIM: { dot: "var(--color-warning)", badge: "warning" },
  REVIEW: { dot: "var(--color-accent-bright)", badge: "accent" },
  REBALANCE: { dot: "var(--color-accent-bright)", badge: "accent" },
  BUY: { dot: "var(--color-success)", badge: "success" },
  ACCUMULATE: { dot: "var(--color-success)", badge: "success" },
  ALERT: { dot: "var(--color-error)", badge: "error" },
};

function PriorityActionRow({ item, onTicker }: { item: PriorityItem; onTicker: (t: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const colors = actionColors[item.type] ?? actionColors.REVIEW;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      style={{
        borderRadius: "var(--radius-md)",
        borderLeft: `3px solid ${item.borderColor}`,
        overflow: "hidden",
        background: `${item.borderColor}08`,
      }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-sm)",
          padding: "var(--space-md) var(--space-lg)",
          width: "100%",
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: "var(--font-sans)",
          color: "var(--color-text)",
        }}
      >
        {item.source === "alert" && <AlertTriangle size={13} color="var(--color-error)" style={{ flexShrink: 0 }} />}
        <Badge variant={colors.badge} size="sm">{item.type}</Badge>
        {item.ticker && (
          <span style={{
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            fontSize: "var(--text-sm)",
            color: "var(--color-text)",
          }}>
            {item.ticker}
          </span>
        )}
        <span style={{
          flex: 1,
          fontSize: "var(--text-xs)",
          color: "var(--color-text-secondary)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}>
          {item.title}
        </span>
        <motion.div animate={{ rotate: expanded ? 180 : 0 }}>
          <ChevronDown size={14} color="var(--color-text-muted)" />
        </motion.div>
      </button>

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
              padding: "0 var(--space-lg) var(--space-md)",
              fontSize: "var(--text-xs)",
              color: "var(--color-text-secondary)",
              lineHeight: 1.5,
            }}>
              {item.detail}

              {/* Agent stance tiles (actions only) */}
              {item.action?.agent_summary && item.action.agent_summary.length > 0 && (
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginTop: "var(--space-sm)",
                  flexWrap: "wrap",
                }}>
                  {item.action.agent_summary.map((a) => {
                    const sentColor = a.sentiment >= 0.3 ? "var(--color-success)" : a.sentiment <= -0.3 ? "var(--color-error)" : "var(--color-text-muted)";
                    const agentColors: Record<string, string> = {
                      warren: "#34d399", auditor: "#fbbf24", klarman: "#60a5fa",
                      soros: "#f472b6", druckenmiller: "#c084fc", dalio: "#fb923c",
                      simons: "#a78bfa", lynch: "#38bdf8", data_analyst: "#94a3b8",
                    };
                    const agentInitials: Record<string, string> = {
                      warren: "WB", auditor: "RA", klarman: "SK",
                      soros: "GS", druckenmiller: "SD", dalio: "RD",
                      simons: "JS", lynch: "PL", data_analyst: "DA",
                    };
                    const bg = agentColors[a.agent] ?? "var(--color-text-muted)";
                    const initials = agentInitials[a.agent] ?? a.agent.charAt(0).toUpperCase();
                    return (
                      <div
                        key={a.agent}
                        title={`${a.agent}: ${a.summary || (a.sentiment > 0 ? "Bullish" : a.sentiment < 0 ? "Bearish" : "Neutral")}`}
                        style={{
                          width: 24, height: 24,
                          borderRadius: 4,
                          background: `${sentColor}18`,
                          border: `1.5px solid ${bg}`,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 8, fontWeight: 700, fontFamily: "var(--font-mono)",
                          color: bg,
                          cursor: "default",
                        }}
                      >
                        {initials}
                      </div>
                    );
                  })}
                  {item.action.consensus_score != null && (
                    <span style={{
                      fontSize: 10, fontFamily: "var(--font-mono)",
                      color: "var(--color-text-muted)", marginLeft: 2,
                    }}>
                      cs:{(item.action.consensus_score ?? 0) > 0 ? "+" : ""}{(item.action.consensus_score ?? 0).toFixed(2)}
                    </span>
                  )}
                </div>
              )}

              {item.ticker && (
                <button
                  onClick={(e) => { e.stopPropagation(); onTicker(item.ticker!); }}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    marginTop: "var(--space-sm)",
                    padding: "2px 8px",
                    background: "var(--color-accent-ghost)",
                    border: "1px solid rgba(99,102,241,0.15)",
                    borderRadius: "var(--radius-full)",
                    color: "var(--color-accent-bright)",
                    cursor: "pointer",
                    fontSize: 10,
                    fontWeight: 600,
                    fontFamily: "var(--font-sans)",
                  }}
                >
                  Deep Dive <ArrowRight size={10} />
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Mini Success Ring (for opportunity cards)
// ═══════════════════════════════════════════════════════════════════

function MiniSuccessRing({ value, size = 36 }: { value: number | null; size?: number }) {
  const pct = value != null ? Math.max(0, Math.min(100, value)) : 0;
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 70 ? "var(--color-success)" : pct >= 50 ? "var(--color-warning)" : "var(--color-text-muted)";

  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-surface-2)" strokeWidth={3} />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth={3}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)",
        color,
      }}>
        {value != null ? `${Math.round(value)}` : "—"}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Thesis Health Dots
// ═══════════════════════════════════════════════════════════════════

const healthColors: Record<string, string> = {
  INTACT: "var(--color-success)",
  UNDER_REVIEW: "var(--color-warning)",
  CHALLENGED: "var(--color-warning)",
  BROKEN: "var(--color-error)",
};

function ThesisHealthDots({
  positions,
  onTicker,
}: {
  positions: ThesisPosition[];
  onTicker: (t: string) => void;
}) {
  if (!positions.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: "var(--space-sm)" }}>
      {positions.map((p) => (
        <motion.button
          key={p.ticker}
          onClick={() => onTicker(p.ticker)}
          whileHover={{ scale: 1.2 }}
          whileTap={{ scale: 0.9 }}
          title={`${p.ticker}: ${p.thesis_health} (${p.pnl_pct >= 0 ? "+" : ""}${(p.pnl_pct ?? 0).toFixed(1)}%)`}
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 2,
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: 0,
          }}
        >
          <div style={{
            width: 14,
            height: 14,
            borderRadius: "50%",
            background: healthColors[p.thesis_health] ?? "var(--color-text-muted)",
            boxShadow: `0 0 6px ${healthColors[p.thesis_health] ?? "transparent"}`,
          }} />
          <span style={{
            fontSize: 8,
            fontWeight: 600,
            fontFamily: "var(--font-mono)",
            color: "var(--color-text-muted)",
          }}>
            {p.ticker}
          </span>
        </motion.button>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Today View
// ═══════════════════════════════════════════════════════════════════

export function Today() {
  const navigate = useNavigate();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const alerts = useStore((s) => s.alerts);
  const { data: briefing, loading: briefingLoading } = useDailyBriefing();
  const { actions, loading: actionsLoading } = usePortfolioAdvisor();
  const { positions: thesisPositions, loading: thesisLoading } = useThesisSummary();
  const { totalValue, dayPnl, dayPnlPct, loading: portfolioLoading } = usePortfolio();
  const { items: topRecs, totalNew, loading: recsLoading } = useTopRecommendations(3);

  // Merge alerts + advisor actions into unified priority list (filter out HOLD)
  const priorityItems = useMemo(() => {
    const items: PriorityItem[] = [];

    // Add advisor actions (skip HOLD — not actionable)
    for (const a of actions) {
      if (a.type === "HOLD") continue;
      const colors = actionColors[a.type] ?? actionColors.REVIEW;
      items.push({
        key: `action-${a.type}-${a.ticker}`,
        source: "action",
        type: a.type,
        ticker: a.ticker,
        title: a.title,
        detail: a.reasoning || a.detail,
        urgency: urgencyOrder[a.type] ?? 5,
        badgeVariant: colors.badge,
        borderColor: colors.dot,
        action: a,
      });
    }

    // Add alerts (skip acknowledged)
    for (const al of alerts) {
      if (al.acknowledged) continue;
      // Skip if we already have an action for this ticker
      if (al.ticker && items.some((i) => i.ticker === al.ticker)) continue;
      const sev = al.severity;
      const borderColor = sev === "critical" || sev === "error" ? "var(--color-error)" : "var(--color-warning)";
      items.push({
        key: `alert-${al.id}`,
        source: "alert",
        type: "ALERT",
        ticker: al.ticker ?? null,
        title: al.title,
        detail: al.message,
        urgency: urgencyOrder[sev] ?? 1,
        badgeVariant: sev === "critical" || sev === "error" ? "error" : "warning",
        borderColor,
        alert: al,
      });
    }

    // Sort by urgency (lower = more urgent)
    items.sort((a, b) => a.urgency - b.urgency);
    return items;
  }, [actions, alerts]);

  // Headline directive
  const headline = useMemo(() => {
    const criticalAlerts = alerts.filter((a) => !a.acknowledged && (a.severity === "critical" || a.severity === "error"));
    if (criticalAlerts.length > 0) {
      return `${criticalAlerts.length} critical alert${criticalAlerts.length > 1 ? "s" : ""} — review immediately`;
    }
    if (priorityItems.length > 0) {
      return `${priorityItems.length} position${priorityItems.length > 1 ? "s" : ""} need${priorityItems.length === 1 ? "s" : ""} attention`;
    }
    if (totalNew > 0) {
      return `${totalNew} new pick${totalNew > 1 ? "s" : ""} to review`;
    }
    return "Portfolio on track — no action needed today";
  }, [alerts, priorityItems.length, totalNew]);

  // Pendulum label
  const pendulumLabelMap: Record<string, string> = {
    extreme_fear: "Extreme Fear",
    fear: "Fear",
    neutral: "Neutral",
    greed: "Greed",
    extreme_greed: "Extreme Greed",
  };
  const pendulumColor = (score: number) => {
    if (score < 25) return "var(--color-error)";
    if (score < 40) return "var(--color-warning)";
    if (score < 60) return "var(--color-text-secondary)";
    return "var(--color-success)";
  };

  const isLoading = briefingLoading || portfolioLoading;

  return (
    <div style={{
      height: "100%",
      overflowY: "auto",
      paddingBottom: "calc(var(--nav-height) + var(--safe-bottom) + var(--space-xl))",
    }}>
      <ViewHeader
        title="Today"
        subtitle={new Date().toLocaleDateString("en-US", {
          weekday: "long",
          month: "long",
          day: "numeric",
        })}
      />

      <div style={{
        padding: "var(--space-lg)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-lg)",
      }}>

        {/* ═══════ Section 1: Headline Card ═══════ */}
        <BentoCard variant="hero" glow>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-sm)",
            marginBottom: "var(--space-md)",
          }}>
            <Sunrise size={14} color="var(--color-accent-bright)" />
            <span style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--color-accent-bright)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}>
              Daily Directive
            </span>
          </div>

          {isLoading ? (
            <div className="skeleton" style={{ height: 80, borderRadius: "var(--radius-md)" }} />
          ) : (
            <>
              <div style={{
                fontSize: "var(--text-lg)",
                fontWeight: 700,
                color: "var(--color-text)",
                lineHeight: 1.3,
                marginBottom: "var(--space-md)",
              }}>
                {headline}
              </div>

              {/* Inline metrics row */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-lg)",
                flexWrap: "wrap",
              }}>
                {/* Portfolio value */}
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{
                    fontSize: "var(--text-2xs)",
                    color: "var(--color-text-muted)",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}>
                    Value
                  </span>
                  <AnimatedNumber
                    value={totalValue}
                    format={fmtCurrency}
                    style={{
                      fontSize: "var(--text-base)",
                      fontWeight: 700,
                      fontFamily: "var(--font-mono)",
                      color: "var(--color-text)",
                    }}
                  />
                </div>

                {/* Day P&L */}
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{
                    fontSize: "var(--text-2xs)",
                    color: "var(--color-text-muted)",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}>
                    Day P&L
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    {dayPnl > 0 ? (
                      <TrendingUp size={12} color="var(--color-success)" />
                    ) : dayPnl < 0 ? (
                      <TrendingDown size={12} color="var(--color-error)" />
                    ) : (
                      <Minus size={12} color="var(--color-text-muted)" />
                    )}
                    <span style={{
                      fontSize: "var(--text-base)",
                      fontWeight: 700,
                      fontFamily: "var(--font-mono)",
                      color: dayPnl >= 0 ? "var(--color-success)" : "var(--color-error)",
                    }}>
                      {fmtPnl(dayPnl)}
                    </span>
                    <span style={{
                      fontSize: 10,
                      fontFamily: "var(--font-mono)",
                      color: dayPnlPct >= 0 ? "var(--color-success)" : "var(--color-error)",
                    }}>
                      ({dayPnlPct >= 0 ? "+" : ""}{(dayPnlPct ?? 0).toFixed(2)}%)
                    </span>
                  </div>
                </div>

                {/* Pendulum score (compact badge) */}
                {briefing && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{
                      fontSize: "var(--text-2xs)",
                      color: "var(--color-text-muted)",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                    }}>
                      Sentiment
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span style={{
                        fontSize: "var(--text-base)",
                        fontWeight: 700,
                        fontFamily: "var(--font-mono)",
                        color: pendulumColor(briefing.pendulumScore),
                      }}>
                        {Math.round(briefing.pendulumScore)}
                      </span>
                      <span style={{
                        fontSize: 10,
                        color: pendulumColor(briefing.pendulumScore),
                        fontWeight: 600,
                      }}>
                        {pendulumLabelMap[briefing.pendulumLabel] ?? briefing.pendulumLabel}
                      </span>
                    </div>
                    {briefing.pendulumComponents && (
                      <div style={{ display: "flex", gap: 6, marginTop: 2 }}>
                        {([
                          ["VIX", briefing.pendulumComponents.vix],
                          ["Credit", briefing.pendulumComponents.creditSpread],
                          ["P/C", briefing.pendulumComponents.putCall],
                          ["Mom", briefing.pendulumComponents.momentum],
                        ] as [string, number | null][])
                          .filter(([, v]) => v != null)
                          .map(([label, val]) => (
                            <span key={label} style={{
                              fontSize: 9,
                              fontFamily: "var(--font-mono)",
                              color: pendulumColor(val!),
                              opacity: 0.8,
                            }}>
                              {label}:{val}
                            </span>
                          ))}
                      </div>
                    )}
                    {briefing.sizingMultiplier != null && briefing.sizingMultiplier !== 1.0 && (
                      <span style={{
                        fontSize: 9, fontFamily: "var(--font-mono)",
                        color: briefing.sizingMultiplier < 1 ? "var(--color-warning)" : "var(--color-success)",
                      }}>
                        sizing: {((briefing.sizingMultiplier ?? 1) * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </BentoCard>

        {/* ═══════ Section 2: Priority Actions ═══════ */}
        <BentoCard title={priorityItems.length > 0 ? `Priority Actions (${priorityItems.length})` : "Priority Actions"}>
          {actionsLoading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton" style={{ height: 44, borderRadius: "var(--radius-md)" }} />
              ))}
            </div>
          ) : priorityItems.length === 0 ? (
            <div style={{
              padding: "var(--space-xl)",
              textAlign: "center",
              color: "var(--color-text-muted)",
              fontSize: "var(--text-sm)",
            }}>
              No actions needed today. Portfolio is on track.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {priorityItems.map((item) => (
                <PriorityActionRow
                  key={item.key}
                  item={item}
                  onTicker={(t) => setOverlayTicker(t)}
                />
              ))}
            </div>
          )}
        </BentoCard>

        {/* ═══════ Section 3: New Opportunities ═══════ */}
        {!recsLoading && topRecs.length > 0 && (
          <BentoCard title={`New Opportunities (${totalNew})`}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {topRecs.map((rec) => (
                <motion.button
                  key={rec.ticker}
                  onClick={() => setOverlayTicker(rec.ticker)}
                  whileTap={{ scale: 0.98 }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-md)",
                    padding: "var(--space-md)",
                    background: "var(--color-surface-1)",
                    borderRadius: "var(--radius-md)",
                    border: "none",
                    cursor: "pointer",
                    width: "100%",
                    textAlign: "left",
                    fontFamily: "var(--font-sans)",
                    color: "var(--color-text)",
                  }}
                >
                  <MiniSuccessRing value={rec.successProbability} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{
                        fontWeight: 700,
                        fontSize: "var(--text-sm)",
                        fontFamily: "var(--font-mono)",
                      }}>
                        {rec.ticker}
                      </span>
                      <Badge variant={verdictBadgeVariant[rec.verdict] ?? "neutral"} size="sm">
                        {verdictLabel[rec.verdict] ?? rec.verdict}
                      </Badge>
                    </div>
                    <div style={{
                      fontSize: "var(--text-xs)",
                      color: "var(--color-text-secondary)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      marginTop: 2,
                    }}>
                      {rec.name}
                    </div>
                  </div>
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <div style={{
                      fontSize: "var(--text-sm)",
                      fontWeight: 600,
                      fontFamily: "var(--font-mono)",
                    }}>
                      ${(rec.currentPrice ?? 0).toFixed(2)}
                    </div>
                    {rec.changePct != null && (
                      <div style={{
                        fontSize: 10,
                        fontFamily: "var(--font-mono)",
                        color: rec.changePct >= 0 ? "var(--color-success)" : "var(--color-error)",
                      }}>
                        {rec.changePct >= 0 ? "+" : ""}{rec.changePct.toFixed(2)}%
                      </div>
                    )}
                  </div>
                  <ChevronRight size={14} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
                </motion.button>
              ))}

              {totalNew > topRecs.length && (
                <button
                  onClick={() => navigate("/recommendations")}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                    padding: "var(--space-sm)",
                    background: "none",
                    border: "none",
                    color: "var(--color-accent-bright)",
                    fontSize: "var(--text-xs)",
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: "var(--font-sans)",
                  }}
                >
                  See all {totalNew} picks <ChevronRight size={14} />
                </button>
              )}
            </div>
          </BentoCard>
        )}

        {/* ═══════ Section 4: Portfolio Health ═══════ */}
        {!thesisLoading && thesisPositions.length > 0 && (
          <BentoCard title="Portfolio Health">
            <div style={{
              fontSize: "var(--text-sm)",
              color: "var(--color-text-secondary)",
              marginBottom: "var(--space-xs)",
            }}>
              {(() => {
                const healthy = thesisPositions.filter((p) => p.thesis_health === "INTACT").length;
                const review = thesisPositions.filter((p) => p.thesis_health === "UNDER_REVIEW" || p.thesis_health === "CHALLENGED").length;
                const broken = thesisPositions.filter((p) => p.thesis_health === "BROKEN").length;
                const parts: string[] = [];
                if (healthy > 0) parts.push(`${healthy} healthy`);
                if (review > 0) parts.push(`${review} under review`);
                if (broken > 0) parts.push(`${broken} broken`);
                return parts.join(", ");
              })()}
            </div>
            <ThesisHealthDots
              positions={thesisPositions}
              onTicker={(t) => setOverlayTicker(t)}
            />
          </BentoCard>
        )}

      </div>
    </div>
  );
}
