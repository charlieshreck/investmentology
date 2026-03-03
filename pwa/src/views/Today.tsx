import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Sunrise, ChevronDown, ChevronRight, AlertTriangle,
  TrendingUp, TrendingDown, Minus, ArrowRight, RefreshCw,
} from "lucide-react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { AnimatedNumber } from "../components/shared/AnimatedNumber";
import { useStore } from "../stores/useStore";
import { usePortfolio } from "../hooks/usePortfolio";
import { useDailyBriefing, usePortfolioAdvisor, useThesisSummary } from "../hooks/useToday";
import type { AdvisorAction, ThesisPosition } from "../hooks/useToday";

// ═══════════════════════════════════════════════════════════════════
// Market Pendulum — SVG arc gauge
// ═══════════════════════════════════════════════════════════════════

function MarketPendulum({ score, label }: { score: number; label: string }) {
  // score: 0 = extreme fear, 50 = neutral, 100 = extreme greed
  const clampedScore = Math.max(0, Math.min(100, score));
  const angle = -90 + (clampedScore / 100) * 180; // -90° to +90°

  // Arc path (semi-circle from left to right)
  const cx = 100, cy = 85, r = 70;
  const arcPath = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;

  // Needle endpoint
  const rad = (angle * Math.PI) / 180;
  const nx = cx + Math.cos(rad) * (r - 8);
  const ny = cy + Math.sin(rad) * (r - 8);

  // Colour based on score
  const getColor = (s: number) => {
    if (s < 25) return "var(--color-error)";
    if (s < 40) return "var(--color-warning)";
    if (s < 60) return "var(--color-text-secondary)";
    if (s < 75) return "var(--color-success)";
    return "var(--color-success)";
  };
  const needleColor = getColor(clampedScore);

  const labelMap: Record<string, string> = {
    extreme_fear: "Extreme Fear",
    fear: "Fear",
    neutral: "Neutral",
    greed: "Greed",
    extreme_greed: "Extreme Greed",
  };
  const displayLabel = labelMap[label] ?? label;

  const sentenceMap: Record<string, string> = {
    extreme_fear: "Markets are extremely fearful — historically a strong buying environment.",
    fear: "Markets are fearful — historically a buying environment.",
    neutral: "Markets are balanced — no strong directional bias.",
    greed: "Markets are greedy — exercise caution on new positions.",
    extreme_greed: "Markets are extremely greedy — consider taking profits.",
  };
  const sentence = sentenceMap[label] ?? "Market sentiment data available.";

  return (
    <div style={{ textAlign: "center" }}>
      <svg viewBox="0 0 200 100" width="100%" style={{ maxWidth: 280 }}>
        {/* Background arc */}
        <path
          d={arcPath}
          fill="none"
          stroke="var(--color-surface-2)"
          strokeWidth={12}
          strokeLinecap="round"
        />
        {/* Gradient arc — filled to current score */}
        <defs>
          <linearGradient id="pendulum-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--color-error)" />
            <stop offset="35%" stopColor="var(--color-warning)" />
            <stop offset="50%" stopColor="var(--color-text-muted)" />
            <stop offset="75%" stopColor="var(--color-success)" />
            <stop offset="100%" stopColor="var(--color-success)" />
          </linearGradient>
        </defs>
        <path
          d={arcPath}
          fill="none"
          stroke="url(#pendulum-grad)"
          strokeWidth={12}
          strokeLinecap="round"
          opacity={0.3}
        />
        {/* Needle */}
        <motion.line
          x1={cx}
          y1={cy}
          initial={{ x2: cx, y2: cy }}
          animate={{ x2: nx, y2: ny }}
          transition={{ type: "spring", stiffness: 80, damping: 20 }}
          stroke={needleColor}
          strokeWidth={3}
          strokeLinecap="round"
        />
        {/* Center dot */}
        <circle cx={cx} cy={cy} r={5} fill={needleColor} />
        {/* Score label */}
        <text
          x={cx}
          y={cy - 20}
          textAnchor="middle"
          fill="var(--color-text)"
          fontSize={22}
          fontWeight={700}
          fontFamily="var(--font-mono)"
        >
          {Math.round(clampedScore)}
        </text>
        {/* Fear / Greed labels */}
        <text x={cx - r + 4} y={cy + 16} textAnchor="start" fill="var(--color-error)" fontSize={9} fontWeight={600}>
          FEAR
        </text>
        <text x={cx + r - 4} y={cy + 16} textAnchor="end" fill="var(--color-success)" fontSize={9} fontWeight={600}>
          GREED
        </text>
      </svg>
      <div style={{
        marginTop: 4,
        fontSize: "var(--text-sm)",
        fontWeight: 600,
        color: needleColor,
      }}>
        {displayLabel}
      </div>
      <div style={{
        marginTop: 6,
        fontSize: "var(--text-xs)",
        color: "var(--color-text-secondary)",
        lineHeight: 1.4,
        maxWidth: 320,
        margin: "6px auto 0",
      }}>
        {sentence}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// Action Queue Row
// ═══════════════════════════════════════════════════════════════════

const actionColors: Record<string, { bg: string; dot: string; badge: "error" | "warning" | "accent" | "success" | "neutral" }> = {
  SELL: { bg: "rgba(248,113,113,0.06)", dot: "var(--color-error)", badge: "error" },
  TRIM: { bg: "rgba(251,191,36,0.06)", dot: "var(--color-warning)", badge: "warning" },
  REVIEW: { bg: "rgba(99,102,241,0.06)", dot: "var(--color-accent-bright)", badge: "accent" },
  REBALANCE: { bg: "rgba(99,102,241,0.06)", dot: "var(--color-accent-bright)", badge: "accent" },
  BUY: { bg: "rgba(52,211,153,0.06)", dot: "var(--color-success)", badge: "success" },
};

function ActionRow({ action, onTicker }: { action: AdvisorAction; onTicker: (t: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const colors = actionColors[action.type] ?? actionColors.REVIEW;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      style={{
        background: colors.bg,
        borderRadius: "var(--radius-md)",
        borderLeft: `3px solid ${colors.dot}`,
        overflow: "hidden",
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
        <Badge variant={colors.badge} size="sm">{action.type}</Badge>
        {action.ticker && (
          <span style={{
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            fontSize: "var(--text-sm)",
            color: "var(--color-text)",
          }}>
            {action.ticker}
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
          {action.title}
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
              {action.reasoning}
              {action.ticker && (
                <button
                  onClick={(e) => { e.stopPropagation(); onTicker(action.ticker!); }}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    marginLeft: 8,
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
          title={`${p.ticker}: ${p.thesis_health} (${p.pnl_pct >= 0 ? "+" : ""}${p.pnl_pct.toFixed(1)}%)`}
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

const fmtCurrency = (n: number) =>
  "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

const fmtPnl = (n: number) =>
  (n >= 0 ? "+" : "") + "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

export function Today() {
  const navigate = useNavigate();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const { data: briefing, loading: briefingLoading } = useDailyBriefing();
  const { actions, loading: actionsLoading } = usePortfolioAdvisor();
  const { positions: thesisPositions, loading: thesisLoading } = useThesisSummary();
  const { totalValue, dayPnl, dayPnlPct, loading: portfolioLoading } = usePortfolio();

  const [showAllActions, setShowAllActions] = useState(false);
  const visibleActions = showAllActions ? actions : actions.slice(0, 5);
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

        {/* ═══════ Market Pendulum ═══════ */}
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
              Market Sentiment
            </span>
          </div>
          {briefingLoading ? (
            <div className="skeleton" style={{ height: 120, borderRadius: "var(--radius-md)" }} />
          ) : briefing ? (
            <MarketPendulum
              score={briefing.pendulumScore}
              label={briefing.pendulumLabel}
            />
          ) : (
            <div style={{ textAlign: "center", padding: "var(--space-xl)", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
              Market data unavailable
            </div>
          )}
        </BentoCard>

        {/* ═══════ Action Queue ═══════ */}
        <BentoCard title="Action Queue">
          {actionsLoading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton" style={{ height: 44, borderRadius: "var(--radius-md)" }} />
              ))}
            </div>
          ) : actions.length === 0 ? (
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
              {visibleActions.map((action, i) => (
                <ActionRow
                  key={`${action.type}-${action.ticker}-${i}`}
                  action={action}
                  onTicker={(t) => setOverlayTicker(t)}
                />
              ))}
              {actions.length > 5 && (
                <button
                  onClick={() => setShowAllActions(!showAllActions)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--color-accent-bright)",
                    fontSize: "var(--text-xs)",
                    fontWeight: 600,
                    cursor: "pointer",
                    padding: "var(--space-sm)",
                    fontFamily: "var(--font-sans)",
                  }}
                >
                  {showAllActions ? "Show less" : `Show all ${actions.length} actions`}
                </button>
              )}
            </div>
          )}
        </BentoCard>

        {/* ═══════ Portfolio Pulse ═══════ */}
        <BentoCard title="Portfolio Pulse">
          {portfolioLoading ? (
            <div className="skeleton" style={{ height: 80, borderRadius: "var(--radius-md)" }} />
          ) : (
            <>
              <div style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr",
                gap: "var(--space-sm)",
              }}>
                {/* Total Value */}
                <div style={{
                  padding: "var(--space-md)",
                  background: "var(--color-surface-1)",
                  borderRadius: "var(--radius-md)",
                  textAlign: "center",
                }}>
                  <div style={{
                    fontSize: "var(--text-2xs)",
                    color: "var(--color-text-muted)",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    marginBottom: 4,
                  }}>
                    Value
                  </div>
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
                <div style={{
                  padding: "var(--space-md)",
                  background: "var(--color-surface-1)",
                  borderRadius: "var(--radius-md)",
                  textAlign: "center",
                }}>
                  <div style={{
                    fontSize: "var(--text-2xs)",
                    color: "var(--color-text-muted)",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    marginBottom: 4,
                  }}>
                    Day P&L
                  </div>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                  }}>
                    {dayPnl > 0 ? (
                      <TrendingUp size={12} color="var(--color-success)" />
                    ) : dayPnl < 0 ? (
                      <TrendingDown size={12} color="var(--color-error)" />
                    ) : (
                      <Minus size={12} color="var(--color-text-muted)" />
                    )}
                    <AnimatedNumber
                      value={dayPnl}
                      format={fmtPnl}
                      style={{
                        fontSize: "var(--text-base)",
                        fontWeight: 700,
                        fontFamily: "var(--font-mono)",
                        color: dayPnl >= 0 ? "var(--color-success)" : "var(--color-error)",
                      }}
                    />
                  </div>
                  <div style={{
                    fontSize: 10,
                    fontFamily: "var(--font-mono)",
                    color: dayPnlPct >= 0 ? "var(--color-success)" : "var(--color-error)",
                    marginTop: 2,
                  }}>
                    {dayPnlPct >= 0 ? "+" : ""}{dayPnlPct.toFixed(2)}%
                  </div>
                </div>

                {/* Positions */}
                <div style={{
                  padding: "var(--space-md)",
                  background: "var(--color-surface-1)",
                  borderRadius: "var(--radius-md)",
                  textAlign: "center",
                }}>
                  <div style={{
                    fontSize: "var(--text-2xs)",
                    color: "var(--color-text-muted)",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    marginBottom: 4,
                  }}>
                    Positions
                  </div>
                  <div style={{
                    fontSize: "var(--text-base)",
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                    color: "var(--color-text)",
                  }}>
                    {thesisPositions.length || "—"}
                  </div>
                </div>
              </div>

              {/* Thesis health dots */}
              {!thesisLoading && thesisPositions.length > 0 && (
                <div style={{ marginTop: "var(--space-md)" }}>
                  <div style={{
                    fontSize: "var(--text-2xs)",
                    color: "var(--color-text-muted)",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    marginBottom: 4,
                  }}>
                    Thesis Health
                  </div>
                  <ThesisHealthDots
                    positions={thesisPositions}
                    onTicker={(t) => setOverlayTicker(t)}
                  />
                </div>
              )}

              <button
                onClick={() => navigate("/portfolio")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  marginTop: "var(--space-md)",
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
                View Portfolio <ChevronRight size={14} />
              </button>
            </>
          )}
        </BentoCard>

        {/* ═══════ Alerts ═══════ */}
        {briefing && (briefing.criticalAlertCount > 0 || briefing.alertCount > 0) && (
          <BentoCard variant="error" compact>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
            }}>
              <AlertTriangle size={16} color="var(--color-error)" />
              <span style={{
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                color: "var(--color-text)",
              }}>
                {briefing.criticalAlertCount > 0
                  ? `${briefing.criticalAlertCount} critical alert${briefing.criticalAlertCount > 1 ? "s" : ""}`
                  : `${briefing.alertCount} alert${briefing.alertCount > 1 ? "s" : ""}`
                }
              </span>
              <button
                onClick={() => navigate("/portfolio")}
                style={{
                  marginLeft: "auto",
                  background: "none",
                  border: "none",
                  color: "var(--color-accent-bright)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "var(--font-sans)",
                }}
              >
                View <ChevronRight size={12} />
              </button>
            </div>
          </BentoCard>
        )}

        {/* ═══════ Quick Links ═══════ */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--space-sm)",
        }}>
          <BentoCard compact interactive>
            <button
              onClick={() => navigate("/recommendations")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                background: "none",
                border: "none",
                color: "var(--color-text)",
                cursor: "pointer",
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                fontFamily: "var(--font-sans)",
                padding: 0,
                width: "100%",
              }}
            >
              <TrendingUp size={16} color="var(--color-success)" />
              Top Picks
              <ChevronRight size={14} color="var(--color-text-muted)" style={{ marginLeft: "auto" }} />
            </button>
          </BentoCard>
          <BentoCard compact interactive>
            <button
              onClick={() => navigate("/watchlist")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                background: "none",
                border: "none",
                color: "var(--color-text)",
                cursor: "pointer",
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                fontFamily: "var(--font-sans)",
                padding: 0,
                width: "100%",
              }}
            >
              <RefreshCw size={16} color="var(--color-accent-bright)" />
              Watchlist
              <ChevronRight size={14} color="var(--color-text-muted)" style={{ marginLeft: "auto" }} />
            </button>
          </BentoCard>
        </div>

      </div>
    </div>
  );
}
