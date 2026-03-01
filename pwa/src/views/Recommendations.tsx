import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { RecommendationCardSkeleton } from "../components/shared/SkeletonCard";
import { MarketStatus } from "../components/shared/MarketStatus";
import { AddToPortfolioModal } from "../components/shared/AddToPortfolioModal";
import { useRecommendations } from "../hooks/useRecommendations";
import { verdictColor, verdictLabel, verdictBadgeVariant } from "../utils/verdictHelpers";
import type { Recommendation, AgentStance } from "../types/models";
import { useStore } from "../stores/useStore";
import {
  ChevronDown, Plus, TrendingUp, TrendingDown,
  Rocket, ShoppingCart, Layers, Anchor, Eye, Scissors, DoorOpen, ShieldAlert, Trash2,
  type LucideIcon,
} from "lucide-react";

// ── Creative group header content ──
const verdictGroupMeta: Record<string, { title: string; tagline: string; icon: LucideIcon }> = {
  STRONG_BUY: { title: "High Conviction", tagline: "Maximum confidence \u2014 act with urgency", icon: Rocket },
  BUY:        { title: "Green Light", tagline: "Strong fundamentals, favourable setup", icon: ShoppingCart },
  ACCUMULATE: { title: "Steady Builders", tagline: "Add on dips, build position over time", icon: Layers },
  HOLD:       { title: "Patience Plays", tagline: "Thesis intact \u2014 stay the course", icon: Anchor },
  WATCHLIST:  { title: "On the Radar", tagline: "Interesting but not yet actionable", icon: Eye },
  REDUCE:     { title: "Trim the Sails", tagline: "Take profits or reduce exposure", icon: Scissors },
  SELL:       { title: "Exit Signal", tagline: "Thesis broken \u2014 close position", icon: DoorOpen },
  AVOID:      { title: "Red Flags", tagline: "Fundamental concerns \u2014 stay clear", icon: ShieldAlert },
  DISCARD:    { title: "Off the Table", tagline: "Failed screening criteria", icon: Trash2 },
};

function formatCap(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function formatPrice(n: number): string {
  return n > 0 ? `$${n.toFixed(2)}` : "\u2014";
}

/* ── Signal Pill (unified) ── */
function SignalPill({ label, bg, fg }: { label: string; bg: string; fg: string }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 3,
      padding: "2px 8px", borderRadius: 99, fontSize: 10, fontWeight: 600,
      background: bg, color: fg, letterSpacing: "0.02em", whiteSpace: "nowrap",
    }}>
      {label}
    </span>
  );
}

function buzzPill(buzzLabel?: string) {
  if (!buzzLabel) return null;
  const colors: Record<string, { bg: string; fg: string }> = {
    HIGH: { bg: "rgba(248, 113, 113, 0.15)", fg: "var(--color-error)" },
    ELEVATED: { bg: "rgba(251, 191, 36, 0.15)", fg: "var(--color-warning)" },
    NORMAL: { bg: "rgba(148, 163, 184, 0.12)", fg: "var(--color-text-muted)" },
    QUIET: { bg: "rgba(52, 211, 153, 0.12)", fg: "var(--color-success)" },
  };
  const c = colors[buzzLabel] || colors.NORMAL;
  const prefix = buzzLabel === "HIGH" ? "\u{1F525} " : buzzLabel === "QUIET" ? "\u{1F92B} " : "";
  return <SignalPill label={`${prefix}${buzzLabel}`} bg={c.bg} fg={c.fg} />;
}

function tierPill(tier?: string | null) {
  if (!tier) return null;
  const colors: Record<string, { bg: string; fg: string }> = {
    HIGH_CONVICTION: { bg: "rgba(52, 211, 153, 0.15)", fg: "var(--color-success)" },
    MIXED: { bg: "rgba(251, 191, 36, 0.15)", fg: "var(--color-warning)" },
    CONTRARIAN: { bg: "rgba(168, 85, 247, 0.15)", fg: "#a855f7" },
  };
  const labels: Record<string, string> = {
    HIGH_CONVICTION: "High Conviction",
    MIXED: "Mixed",
    CONTRARIAN: "Contrarian",
  };
  const c = colors[tier] || colors.MIXED;
  return <SignalPill label={labels[tier] || tier} bg={c.bg} fg={c.fg} />;
}

function stabilityPill(label?: string) {
  if (!label || label === "UNKNOWN") return null;
  const colors: Record<string, { bg: string; fg: string }> = {
    STABLE: { bg: "rgba(52, 211, 153, 0.12)", fg: "var(--color-success)" },
    MODERATE: { bg: "rgba(251, 191, 36, 0.12)", fg: "var(--color-warning)" },
    UNSTABLE: { bg: "rgba(248, 113, 113, 0.12)", fg: "var(--color-error)" },
  };
  const c = colors[label] || colors.MODERATE;
  return <SignalPill label={label} bg={c.bg} fg={c.fg} />;
}

function earningsPill(momentum?: { label: string; beatStreak: number }) {
  if (!momentum || momentum.label === "STABLE") return null;
  const isPositive = momentum.label === "STRONG_UPWARD" || momentum.label === "IMPROVING";
  const fg = isPositive ? "var(--color-success)" : "var(--color-error)";
  const bg = isPositive ? "rgba(52, 211, 153, 0.12)" : "rgba(248, 113, 113, 0.12)";
  const short: Record<string, string> = {
    STRONG_UPWARD: "EPS \u2191\u2191",
    IMPROVING: "EPS \u2191",
    WEAKENING: "EPS \u2193",
    DECLINING: "EPS \u2193\u2193",
  };
  const streak = momentum.beatStreak >= 3 ? ` (${momentum.beatStreak}x beat)` : "";
  return <SignalPill label={`${short[momentum.label] || "EPS"}${streak}`} bg={bg} fg={fg} />;
}

/* ── Sparkline (3 month) ── */
function RecSparkline({ ticker }: { ticker: string }) {
  const [points, setPoints] = useState<number[] | null>(null);

  useEffect(() => {
    fetch(`/api/invest/stock/${ticker}/chart?period=3mo`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.data?.length > 1) {
          setPoints(data.data.map((d: any) => d.close as number));
        }
      })
      .catch(() => {});
  }, [ticker]);

  if (!points || points.length < 2) {
    return <div style={{ width: 100, height: 36, background: "var(--color-surface-1)", borderRadius: 6 }} />;
  }

  const w = 100, h = 36;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;

  const toY = (v: number) => h - 3 - ((v - min) / range) * (h - 6);
  const toX = (i: number) => (i / (points.length - 1)) * w;

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p).toFixed(1)}`).join(" ");
  const trend = points[points.length - 1] >= points[0];
  const lineColor = trend ? "var(--color-success)" : "var(--color-error)";
  const fillColor = trend ? "rgba(52,211,153,0.10)" : "rgba(248,113,113,0.10)";
  const areaD = `${pathD} L${w},${h} L0,${h} Z`;

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block", flexShrink: 0 }}>
      <path d={areaD} fill={fillColor} />
      <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={w} cy={toY(points[points.length - 1])} r={2} fill={lineColor} />
    </svg>
  );
}

/* ── Success Ring (bigger) ── */
function SuccessRing({ probability }: { probability: number | null }) {
  if (probability == null) return null;
  const pct = Math.round(probability * 100);
  const color =
    pct >= 70 ? "var(--color-success)" : pct >= 40 ? "var(--color-warning)" : "var(--color-error)";
  const size = 56;
  const stroke = 4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - probability);

  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--color-surface-2)" strokeWidth={stroke}
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={circumference} strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          strokeLinecap="round"
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      }}>
        <span style={{ fontSize: 14, fontWeight: 800, fontFamily: "var(--font-mono)", color, lineHeight: 1 }}>
          {pct}%
        </span>
      </div>
    </div>
  );
}

/* ── Agent Stance Bar (wider) ── */
function AgentBar({ stance }: { stance: AgentStance }) {
  const pct = Math.abs(stance.sentiment) * 100;
  const color = stance.sentiment >= 0 ? "var(--color-success)" : "var(--color-error)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
      <span style={{
        fontSize: 10, color: "var(--color-text-muted)", textTransform: "capitalize",
        fontWeight: 600, width: 38, flexShrink: 0,
      }}>
        {stance.name.charAt(0).toUpperCase() + stance.name.slice(1, 4)}
      </span>
      <div style={{
        flex: 1, height: 5, borderRadius: 3,
        background: "var(--color-surface-2)", overflow: "hidden",
      }}>
        <div style={{ height: "100%", width: `${Math.max(pct, 6)}%`, background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color, fontWeight: 600, width: 28, textAlign: "right" }}>
        {(stance.confidence * 100).toFixed(0)}%
      </span>
    </div>
  );
}

/* ── Main Recommendation Card ── */
function RecCard({
  rec,
  onOpen,
  onAddToPortfolio,
}: {
  rec: Recommendation;
  onOpen: () => void;
  onAddToPortfolio: () => void;
}) {
  const stances = (rec.agentStances || []) as AgentStance[];
  const [expanded, setExpanded] = useState(false);
  const vColor = verdictColor[rec.verdict] || "var(--color-text-muted)";
  const changePct = rec.changePct ?? 0;
  const changePositive = changePct >= 0;
  const probPct = rec.successProbability != null ? Math.round(rec.successProbability * 100) : null;
  const ringColor = probPct != null
    ? (probPct >= 70 ? "var(--color-success)" : probPct >= 40 ? "var(--color-warning)" : "var(--color-error)")
    : vColor;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        borderRadius: "var(--radius-lg)",
        background: "var(--color-surface-0)",
        border: "1px solid var(--glass-border)",
        boxShadow: "var(--shadow-card), inset 0 1px 0 rgba(255,255,255,0.02)",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Top accent line — matches ring color */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 2,
        background: ringColor, opacity: 0.5,
      }} />

      {/* Main card body — clickable to open deep dive */}
      <div
        onClick={onOpen}
        style={{ padding: "var(--space-lg)", cursor: "pointer" }}
      >
        {/* Row 1: Ring + Ticker/Name + Sparkline + Price */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-md)" }}>

          {/* Success ring */}
          <SuccessRing probability={rec.successProbability} />

          {/* Ticker + Name + Confidence */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-sm)" }}>
              <span style={{
                fontWeight: 800, fontFamily: "var(--font-mono)",
                fontSize: "var(--text-lg)", letterSpacing: "0.02em",
              }}>
                {rec.ticker}
              </span>
              <span style={{
                fontSize: "var(--text-xs)", fontWeight: 700, color: vColor,
              }}>
                {verdictLabel[rec.verdict] || rec.verdict}
              </span>
              {rec.confidence != null && (
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {(rec.confidence * 100).toFixed(0)}% conf
                </span>
              )}
            </div>
            {/* Full company name — own line */}
            <div style={{
              fontSize: "var(--text-xs)", color: "var(--color-text-secondary)",
              marginTop: 2, lineHeight: 1.3,
            }}>
              {rec.name}
            </div>
            {/* Sector + Market Cap */}
            <div style={{
              display: "flex", alignItems: "center", gap: "var(--space-sm)", marginTop: 3,
              fontSize: 10, color: "var(--color-text-muted)",
            }}>
              {rec.sector && <span>{rec.sector}</span>}
              {rec.sector && rec.marketCap > 0 && <span style={{ opacity: 0.4 }}>/</span>}
              {rec.marketCap > 0 && <span>{formatCap(rec.marketCap)}</span>}
            </div>
          </div>

          {/* Right column: Sparkline + Price block */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 }}>
            <RecSparkline ticker={rec.ticker} />
            <div style={{ textAlign: "right" }}>
              <div style={{
                fontFamily: "var(--font-mono)", fontSize: "var(--text-base)", fontWeight: 700,
              }}>
                {formatPrice(rec.currentPrice)}
              </div>
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 3, marginTop: 1,
              }}>
                {changePositive
                  ? <TrendingUp size={11} color="var(--color-success)" />
                  : <TrendingDown size={11} color="var(--color-error)" />
                }
                <span style={{
                  fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 600,
                  color: changePositive ? "var(--color-success)" : "var(--color-error)",
                }}>
                  {changePositive ? "+" : ""}{changePct.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Row 2: Agent Stances (wider bars) */}
        {stances.length > 0 && (
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
            gap: "4px var(--space-md)", marginTop: "var(--space-md)",
            padding: "var(--space-sm) var(--space-md)",
            background: "var(--color-surface-1)", borderRadius: "var(--radius-md)",
          }}>
            {stances.map((a) => (
              <AgentBar key={a.name} stance={a} />
            ))}
          </div>
        )}

        {/* Row 3: Signal pills */}
        <div style={{
          display: "flex", gap: "var(--space-xs)", marginTop: "var(--space-md)",
          flexWrap: "wrap", alignItems: "center",
        }}>
          {rec.riskFlags && rec.riskFlags.length > 0 && (
            <SignalPill
              label={`${rec.riskFlags.length} risk${rec.riskFlags.length > 1 ? "s" : ""}`}
              bg="rgba(251, 191, 36, 0.12)" fg="var(--color-warning)"
            />
          )}
          {tierPill(rec.consensusTier)}
          {stabilityPill(rec.stabilityLabel)}
          {buzzPill(rec.buzzLabel)}
          {earningsPill(rec.earningsMomentum)}
          {rec.suggestedLabel && (
            <SignalPill
              label={rec.suggestedLabel}
              bg={{
                core: "rgba(59, 130, 246, 0.12)",
                tactical: "rgba(251, 191, 36, 0.12)",
                income: "rgba(52, 211, 153, 0.12)",
                contrarian: "rgba(168, 85, 247, 0.12)",
              }[rec.suggestedType || "tactical"] || "rgba(251, 191, 36, 0.12)"}
              fg={{
                core: "#3b82f6",
                tactical: "var(--color-warning)",
                income: "var(--color-success)",
                contrarian: "#a855f7",
              }[rec.suggestedType || "tactical"] || "var(--color-warning)"}
            />
          )}
          {rec.contrarianFlag && (
            <SignalPill label={"\u25C6 Contrarian"} bg="rgba(168, 85, 247, 0.15)" fg="#a855f7" />
          )}
          {rec.dividendYield != null && rec.dividendYield > 0 && (
            <SignalPill
              label={`${rec.dividendYield.toFixed(1)}% div`}
              bg="rgba(52, 211, 153, 0.08)" fg="var(--color-success)"
            />
          )}
          {rec.consensusScore != null && (
            <SignalPill
              label={`Score ${rec.consensusScore > 0 ? "+" : ""}${rec.consensusScore.toFixed(2)}`}
              bg="rgba(148, 163, 184, 0.08)" fg="var(--color-text-secondary)"
            />
          )}
        </div>

        {/* Held position thesis strip */}
        {rec.heldPosition && (
          <div style={{
            marginTop: "var(--space-sm)", padding: "var(--space-sm) var(--space-md)",
            borderRadius: "var(--radius-md)",
            background: "var(--color-surface-1)", border: "1px solid var(--glass-border)",
            display: "flex", alignItems: "center", gap: "var(--space-sm)", flexWrap: "wrap",
          }}>
            <span style={{
              fontSize: 10, fontWeight: 700, color: "var(--color-accent-bright)",
            }}>
              HELD — {rec.heldPosition.positionType}
            </span>
            <span style={{
              fontSize: 10, fontWeight: 600,
              color: {
                INTACT: "var(--color-success)",
                UNDER_REVIEW: "var(--color-warning)",
                CHALLENGED: "var(--color-error)",
                BROKEN: "var(--color-error)",
              }[rec.heldPosition.thesisHealth] || "var(--color-text-muted)",
            }}>
              {"\u25CF"} Thesis {rec.heldPosition.thesisHealth.replace("_", " ").toLowerCase()}
            </span>
            <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
              {rec.heldPosition.daysHeld}d held
            </span>
            <span style={{
              fontSize: 10, fontFamily: "var(--font-mono)",
              color: rec.heldPosition.pnlPct >= 0 ? "var(--color-success)" : "var(--color-error)",
            }}>
              {rec.heldPosition.pnlPct >= 0 ? "+" : ""}{rec.heldPosition.pnlPct.toFixed(1)}%
            </span>
            {rec.heldPosition.entryThesis && (
              <span style={{
                fontSize: 10, color: "var(--color-text-muted)", fontStyle: "italic",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                maxWidth: 300,
              }}>
                &ldquo;{rec.heldPosition.entryThesis}&rdquo;
              </span>
            )}
          </div>
        )}
      </div>

      {/* Bottom bar: Why + Add to Portfolio */}
      <div style={{
        display: "flex", alignItems: "center",
        borderTop: "1px solid var(--glass-border)",
        background: "var(--color-surface-1)",
      }}>
        {/* Why this category — expand toggle */}
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
          style={{
            flex: 1, display: "flex", alignItems: "center", gap: "var(--space-sm)",
            padding: "var(--space-sm) var(--space-lg)",
            background: "none", border: "none", cursor: "pointer",
            color: "var(--color-text-muted)", fontSize: "var(--text-xs)", fontWeight: 500,
            fontFamily: "var(--font-sans)", textAlign: "left",
          }}
        >
          <ChevronDown
            size={14}
            style={{
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.2s ease",
            }}
          />
          <span>Why {verdictLabel[rec.verdict] || rec.verdict}?</span>
        </button>

        {/* Add to portfolio */}
        <button
          onClick={(e) => { e.stopPropagation(); onAddToPortfolio(); }}
          style={{
            display: "flex", alignItems: "center", gap: 4,
            padding: "var(--space-sm) var(--space-lg)",
            background: "none", border: "none", borderLeft: "1px solid var(--glass-border)",
            cursor: "pointer", color: "var(--color-accent-bright)",
            fontSize: "var(--text-xs)", fontWeight: 600, fontFamily: "var(--font-sans)",
            whiteSpace: "nowrap",
          }}
        >
          <Plus size={14} />
          Portfolio
        </button>
      </div>

      {/* Expandable reasoning panel */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div style={{
              padding: "var(--space-md) var(--space-lg)",
              background: "var(--color-surface-1)",
              borderTop: "1px solid var(--glass-border)",
            }}>
              {/* Main reasoning */}
              {rec.reasoning && (
                <p style={{
                  fontSize: "var(--text-xs)", color: "var(--color-text-secondary)",
                  lineHeight: 1.5, margin: 0,
                }}>
                  {rec.reasoning}
                </p>
              )}

              {/* Agent summaries */}
              {stances.length > 0 && (
                <div style={{
                  display: "flex", flexDirection: "column", gap: "var(--space-sm)",
                  marginTop: "var(--space-md)",
                }}>
                  {stances.filter((a) => a.summary && a.summary !== "Failed to parse LLM response").map((a) => (
                    <div key={a.name} style={{
                      padding: "var(--space-sm) var(--space-md)",
                      background: "var(--color-surface-0)", borderRadius: "var(--radius-md)",
                      border: "1px solid var(--glass-border)",
                    }}>
                      <div style={{
                        display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: 4,
                      }}>
                        <span style={{
                          fontSize: 10, fontWeight: 700, color: "var(--color-accent-bright)",
                          textTransform: "capitalize",
                        }}>
                          {a.name}
                        </span>
                        <span style={{
                          fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600,
                          color: a.sentiment >= 0 ? "var(--color-success)" : "var(--color-error)",
                        }}>
                          {a.sentiment >= 0 ? "+" : ""}{(a.sentiment * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p style={{
                        fontSize: 11, color: "var(--color-text-muted)", lineHeight: 1.4, margin: 0,
                      }}>
                        {a.summary}
                      </p>
                      {a.key_signals.length > 0 && (
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
                          {a.key_signals.map((s, i) => (
                            <span key={i} style={{
                              fontSize: 9, padding: "1px 5px", borderRadius: 4,
                              background: "var(--color-surface-2)", color: "var(--color-text-muted)",
                            }}>
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Portfolio fit reasoning */}
              {rec.portfolioFit && (rec.portfolioFit as any).reasoning && (
                <div style={{
                  marginTop: "var(--space-md)", padding: "var(--space-sm) var(--space-md)",
                  background: "var(--color-surface-0)", borderRadius: "var(--radius-md)",
                  border: "1px solid var(--glass-border)",
                }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "var(--color-accent-bright)" }}>
                    Portfolio Fit
                  </span>
                  <span style={{
                    fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
                    marginLeft: 8, color: "var(--color-text-secondary)",
                  }}>
                    {((rec.portfolioFit as any).score * 100).toFixed(0)}%
                  </span>
                  <p style={{
                    fontSize: 11, color: "var(--color-text-muted)", lineHeight: 1.4,
                    margin: "4px 0 0",
                  }}>
                    {(rec.portfolioFit as any).reasoning}
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function Recommendations() {
  const { groupedByVerdict, totalCount, loading, error, refetch } = useRecommendations();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const [portfolioTarget, setPortfolioTarget] = useState<Recommendation | null>(null);
  const [addStatus, setAddStatus] = useState<string | null>(null);

  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Recommend" />
        <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          <RecommendationCardSkeleton />
          <RecommendationCardSkeleton />
          <RecommendationCardSkeleton />
          <RecommendationCardSkeleton />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "var(--space-xl)", paddingTop: "calc(var(--header-height) + var(--space-xl))" }}>
        <ViewHeader title="Recommend" />
        <BentoCard>
          <p style={{ color: "var(--color-error)" }}>Failed to load: {error}</p>
        </BentoCard>
      </div>
    );
  }

  const verdictOrder = Object.keys(groupedByVerdict);

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Recommend"
        subtitle={`${totalCount} stock${totalCount !== 1 ? "s" : ""} ready for portfolio action`}
        right={<MarketStatus />}
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Status toast */}
        {addStatus && (
          <div style={{
            padding: "var(--space-sm) var(--space-lg)",
            borderRadius: "var(--radius-sm)",
            background: addStatus.startsWith("Error") ? "var(--color-error)" : "var(--color-success)",
            color: "#fff", fontSize: "var(--text-sm)", fontWeight: 500,
          }}>
            {addStatus}
          </div>
        )}

        {/* Verdict group badges */}
        <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
          {verdictOrder.map((v) => (
            <a
              key={v}
              href={`#verdict-${v}`}
              style={{ textDecoration: "none" }}
            >
              <Badge variant={verdictBadgeVariant[v] || "neutral"}>
                {verdictGroupMeta[v]?.title || verdictLabel[v] || v} ({groupedByVerdict[v].length})
              </Badge>
            </a>
          ))}
          <button
            onClick={() => refetch()}
            style={{
              padding: "var(--space-xs) var(--space-md)",
              borderRadius: "var(--radius-full)",
              background: "var(--color-surface-2)",
              border: "1px solid var(--glass-border)",
              color: "var(--color-text-secondary)",
              cursor: "pointer",
              fontSize: "var(--text-xs)",
            }}
          >
            Refresh
          </button>
        </div>

        {/* Empty state */}
        {totalCount === 0 && (
          <BentoCard>
            <div style={{ textAlign: "center", padding: "var(--space-xl)", color: "var(--color-text-muted)" }}>
              No recommendations yet. Stocks need Strong Buy, Buy, or Accumulate verdicts to appear here.
            </div>
          </BentoCard>
        )}

        {/* Verdict groups */}
        {verdictOrder.map((v) => {
          const recs = [...groupedByVerdict[v]].sort((a, b) => (b.successProbability ?? 0) - (a.successProbability ?? 0));
          return (
            <div key={v} id={`verdict-${v}`}>
              {/* Group wrapper — border container for whole category */}
              {(() => {
                const meta = verdictGroupMeta[v];
                const GroupIcon = meta?.icon;
                const groupCol: Record<string, string> = {
                  STRONG_BUY: "#22d3ee",
                  BUY: "#38bdf8",
                  ACCUMULATE: "#4ade80",
                  HOLD: "#fbbf24",
                  WATCHLIST: "#94a3b8",
                  REDUCE: "#fb923c",
                  SELL: "#f87171",
                  AVOID: "#ef4444",
                  DISCARD: "#78716c",
                };
                const vCol = groupCol[v] || verdictColor[v] || "#94a3b8";
                return (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ type: "spring", stiffness: 250, damping: 22 }}
                    style={{
                      borderRadius: 18,
                      border: `1px solid ${vCol}20`,
                      background: `linear-gradient(180deg, ${vCol}08 0%, transparent 120px)`,
                      padding: "0 12px 12px",
                      position: "relative",
                    }}
                  >
                    {/* Header pill — sits at the top of the container */}
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                      padding: "14px 8px",
                    }}>
                      {GroupIcon && (
                        <motion.div
                          animate={{ scale: [1, 1.06, 1] }}
                          transition={{ duration: 3, repeat: Infinity, repeatDelay: 5 }}
                          style={{
                            width: 44, height: 44,
                            display: "flex", alignItems: "center", justifyContent: "center",
                            flexShrink: 0,
                            filter: `drop-shadow(0 2px 8px ${vCol}50) drop-shadow(0 0 18px ${vCol}25)`,
                          }}
                        >
                          <GroupIcon size={36} color={vCol} strokeWidth={1.8} />
                        </motion.div>
                      )}

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                          <span style={{
                            fontSize: 18, fontWeight: 600,
                            color: "var(--color-text)",
                            letterSpacing: "-0.01em",
                            lineHeight: 1,
                          }}>
                            {meta?.title || verdictLabel[v] || v}
                          </span>
                          <span style={{
                            fontSize: 12, fontWeight: 600, color: vCol,
                            opacity: 0.8,
                          }}>
                            {recs.length}
                          </span>
                        </div>
                        <div style={{
                          fontSize: 12, color: "var(--color-text-muted)",
                          marginTop: 4, fontWeight: 400,
                        }}>
                          {meta?.tagline || ""}
                        </div>
                      </div>
                    </div>

                    {/* Cards inside the container */}
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)", marginTop: 8 }}>
                {recs.map((rec, i) => (
                  <motion.div
                    key={rec.ticker}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                  >
                    <RecCard
                      rec={rec}
                      onOpen={() => setOverlayTicker(rec.ticker)}
                      onAddToPortfolio={() => setPortfolioTarget(rec)}
                    />
                  </motion.div>
                ))}
              </div>
                  </motion.div>
                );
              })()}
            </div>
          );
        })}

        <div style={{ height: "var(--nav-height)" }} />
      </div>

      {/* Add to Portfolio Modal */}
      {portfolioTarget && (
        <AddToPortfolioModal
          ticker={portfolioTarget.ticker}
          currentPrice={portfolioTarget.currentPrice}
          defaultThesis={portfolioTarget.reasoning || ""}
          onClose={() => setPortfolioTarget(null)}
          onSuccess={(msg) => { setAddStatus(msg); setTimeout(() => setAddStatus(null), 3000); }}
          onError={(msg) => { setAddStatus(msg); setTimeout(() => setAddStatus(null), 3000); }}
        />
      )}
    </div>
  );
}
