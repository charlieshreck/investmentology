import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { RecommendationCardSkeleton } from "../components/shared/SkeletonCard";
import { MarketStatus } from "../components/shared/MarketStatus";
import { AddToPortfolioModal } from "../components/shared/AddToPortfolioModal";
import { AgentConsensusPanel } from "../components/shared/AgentConsensusPanel";
import { SignalTagCloud } from "../components/shared/SignalTagCloud";
import { PriceRangeBar } from "../components/shared/PriceRangeBar";
import { FormattedProse } from "../components/shared/FormattedProse";
import { PortfolioHealthStrip, SECTOR_RISK_MAP } from "../components/shared/PortfolioHealthStrip";
import { useRecommendations } from "../hooks/useRecommendations";
import { usePullToRefresh } from "../hooks/usePullToRefresh";
import { verdictColor, verdictLabel, verdictBadgeVariant } from "../utils/verdictHelpers";
import type { Recommendation, AgentStance, PredictionCard } from "../types/models";
import { useStore } from "../stores/useStore";
import {
  ChevronDown, Plus, TrendingUp, TrendingDown,
  Rocket, ShoppingCart, Layers, Anchor, Eye, Scissors, DoorOpen, ShieldAlert, Trash2,
  RefreshCw, Clock, AlertTriangle, Target, Shield,
  type LucideIcon,
} from "lucide-react";

// ── Creative group header content ──
const verdictGroupMeta: Record<string, { title: string; tagline: string; icon: LucideIcon }> = {
  STRONG_BUY: { title: "High Conviction", tagline: "Maximum confidence \u2014 act with urgency", icon: Rocket },
  BUY:        { title: "Buy", tagline: "Strong fundamentals, favourable setup", icon: ShoppingCart },
  ACCUMULATE: { title: "Accumulate", tagline: "Add on dips, build position over time", icon: Layers },
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

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "\u2014";
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
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

/* ── Conviction tier config ── */
const CONVICTION_CONFIG: Record<string, { label: string; bg: string; fg: string; icon: string }> = {
  ALL_SIGNALS_ALIGNED: { label: "All Aligned", bg: "rgba(52, 211, 153, 0.15)", fg: "var(--color-success)", icon: "\u2605" },
  HIGH_CONVICTION:     { label: "High",        bg: "rgba(167, 139, 250, 0.15)", fg: "var(--color-accent-bright)", icon: "\u25B2" },
  MODERATE:            { label: "Moderate",     bg: "rgba(251, 191, 36, 0.12)",  fg: "var(--color-warning)", icon: "\u25CF" },
  LOW_CONVICTION:      { label: "Low",          bg: "rgba(148, 163, 184, 0.10)", fg: "var(--color-text-muted)", icon: "\u25BD" },
  MIXED_SIGNALS:       { label: "Mixed",        bg: "rgba(248, 113, 113, 0.12)", fg: "var(--color-error)", icon: "\u26A0" },
};

/* ── Sort controls ── */
const SORT_OPTIONS = [
  { key: "default", label: "Probability" },
  { key: "fit", label: "Portfolio Fit" },
  { key: "upside", label: "Upside %" },
  { key: "rr", label: "R:R Ratio" },
  { key: "confidence", label: "Confidence" },
  { key: "conviction", label: "Conviction" },
] as const;

const CONVICTION_RANK: Record<string, number> = {
  ALL_SIGNALS_ALIGNED: 5,
  HIGH_CONVICTION: 4,
  MODERATE: 3,
  LOW_CONVICTION: 2,
  MIXED_SIGNALS: 1,
};

function sortRecs(recs: Recommendation[], sortKey: string): Recommendation[] {
  return [...recs].sort((a, b) => {
    switch (sortKey) {
      case "upside":
        return (b.predictionCard?.upsidePct ?? -999) - (a.predictionCard?.upsidePct ?? -999);
      case "rr":
        return (b.predictionCard?.riskRewardRatio ?? -999) - (a.predictionCard?.riskRewardRatio ?? -999);
      case "confidence":
        return (b.confidence ?? 0) - (a.confidence ?? 0);
      case "conviction":
        return (CONVICTION_RANK[b.predictionCard?.convictionTier ?? ""] ?? 0)
             - (CONVICTION_RANK[a.predictionCard?.convictionTier ?? ""] ?? 0);
      case "fit":
        return (b.portfolioFit?.score ?? 0) - (a.portfolioFit?.score ?? 0);
      default:
        return (b.successProbability ?? 0) - (a.successProbability ?? 0);
    }
  });
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

/* ── Prediction Hero — compact 4-stat row ── */
function PredictionHero({ card }: { card: PredictionCard }) {
  const rrColor = (card.riskRewardRatio ?? 0) >= 2
    ? "var(--color-success)"
    : (card.riskRewardRatio ?? 0) >= 1
      ? "var(--color-warning)"
      : "var(--color-error)";

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 2,
      marginTop: "var(--space-md)",
      background: "var(--color-surface-1)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--glass-border)",
      overflow: "hidden",
    }}>
      {/* Target */}
      <div style={{
        padding: "8px 4px", textAlign: "center",
        background: "rgba(52, 211, 153, 0.04)",
      }}>
        <div style={{ fontSize: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-text-muted)", marginBottom: 2 }}>
          Target
        </div>
        <div style={{
          fontSize: "var(--text-base)", fontWeight: 800, fontFamily: "var(--font-mono)",
          color: "var(--color-success)",
        }}>
          {fmtPrice(card.compositeTarget)}
        </div>
      </div>

      {/* Current */}
      <div style={{ padding: "8px 4px", textAlign: "center" }}>
        <div style={{ fontSize: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-text-muted)", marginBottom: 2 }}>
          Current
        </div>
        <div style={{
          fontSize: "var(--text-base)", fontWeight: 800, fontFamily: "var(--font-mono)",
          color: "var(--color-text)",
        }}>
          {fmtPrice(card.currentPrice)}
        </div>
      </div>

      {/* Upside */}
      <div style={{
        padding: "8px 4px", textAlign: "center",
        background: card.upsidePct != null && card.upsidePct >= 0
          ? "rgba(52, 211, 153, 0.04)" : "rgba(248, 113, 113, 0.04)",
      }}>
        <div style={{ fontSize: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-text-muted)", marginBottom: 2 }}>
          Upside
        </div>
        <div style={{
          fontSize: "var(--text-base)", fontWeight: 800, fontFamily: "var(--font-mono)",
          color: card.upsidePct != null && card.upsidePct >= 0 ? "var(--color-success)" : "var(--color-error)",
        }}>
          {card.upsidePct != null ? `${card.upsidePct > 0 ? "+" : ""}${card.upsidePct.toFixed(1)}%` : "\u2014"}
        </div>
      </div>

      {/* R:R */}
      <div style={{ padding: "8px 4px", textAlign: "center" }}>
        <div style={{ fontSize: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-text-muted)", marginBottom: 2 }}>
          R:R
        </div>
        <div style={{
          fontSize: "var(--text-base)", fontWeight: 800, fontFamily: "var(--font-mono)",
          color: rrColor,
        }}>
          {card.riskRewardRatio != null ? `${card.riskRewardRatio}:1` : "\u2014"}
        </div>
      </div>
    </div>
  );
}


/* ── Main Recommendation Card ── */
function RecCard({
  rec,
  onOpen,
  onAddToPortfolio,
  underweightCategories,
}: {
  rec: Recommendation;
  onOpen: () => void;
  onAddToPortfolio: () => void;
  underweightCategories?: string[];
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
  const pc = rec.predictionCard;
  const convTier = pc ? (CONVICTION_CONFIG[pc.convictionTier] ?? CONVICTION_CONFIG.MODERATE) : null;
  const adv = rec.adversarialResult;

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

        {/* Row 2: Prediction hero stats (if available) */}
        {pc && pc.compositeTarget != null && (
          <PredictionHero card={pc} />
        )}

        {/* Row 3: Price range bar (if prediction card exists) */}
        {pc && pc.compositeTarget != null && (
          <div style={{
            marginTop: "var(--space-sm)",
            padding: "var(--space-xs) var(--space-sm)",
            background: "var(--color-surface-1)",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--glass-border)",
          }}>
            <PriceRangeBar card={pc} />
          </div>
        )}

        {/* Row 4: Conviction + Hold Period + Earnings badges */}
        {pc && (
          <div style={{
            display: "flex", gap: "var(--space-xs)", marginTop: "var(--space-sm)",
            flexWrap: "wrap", alignItems: "center",
          }}>
            {convTier && (
              <SignalPill
                label={`${convTier.icon} ${convTier.label}`}
                bg={convTier.bg} fg={convTier.fg}
              />
            )}
            {pc.holdingPeriod && (
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 3,
                padding: "2px 8px", borderRadius: 99, fontSize: 10, fontWeight: 600,
                background: "rgba(148, 163, 184, 0.08)", color: "var(--color-text-secondary)",
                whiteSpace: "nowrap",
              }}>
                <Clock size={10} />
                {pc.holdingPeriod}
              </span>
            )}
            {pc.earningsWarning && (
              <span style={{
                display: "inline-flex", alignItems: "center", gap: 3,
                padding: "2px 8px", borderRadius: 99, fontSize: 10, fontWeight: 600,
                background: pc.earningsWarning.toLowerCase().includes("defer") || pc.earningsWarning.toLowerCase().includes("block")
                  ? "rgba(248, 113, 113, 0.12)" : "rgba(251, 191, 36, 0.12)",
                color: pc.earningsWarning.toLowerCase().includes("defer") || pc.earningsWarning.toLowerCase().includes("block")
                  ? "var(--color-error)" : "var(--color-warning)",
                whiteSpace: "nowrap",
              }}>
                <AlertTriangle size={10} />
                {pc.earningsWarning}
              </span>
            )}
            {/* Adversarial verdict badge */}
            {adv && (
              <SignalPill
                label={`Munger: ${adv.verdict}`}
                bg={adv.verdict === "PROCEED" ? "rgba(52, 211, 153, 0.12)"
                  : adv.verdict === "CAUTION" ? "rgba(251, 191, 36, 0.12)"
                  : "rgba(248, 113, 113, 0.12)"}
                fg={adv.verdict === "PROCEED" ? "var(--color-success)"
                  : adv.verdict === "CAUTION" ? "var(--color-warning)"
                  : "var(--color-error)"}
              />
            )}
          </div>
        )}

        {/* Row 5: Agent consensus segments — proportional fill */}
        {stances.length > 0 && (() => {
          const bulls = stances.filter((s) => s.sentiment >= 0.15);
          const bears = stances.filter((s) => s.sentiment <= -0.15);
          const holds = stances.filter((s) => s.sentiment > -0.15 && s.sentiment < 0.15);
          const segments: { count: number; label: string; bg: string; fg: string }[] = [];
          if (bulls.length) segments.push({
            count: bulls.length, label: `${bulls.length} Bullish`,
            bg: "rgba(52, 211, 153, 0.15)", fg: "var(--color-success)",
          });
          if (holds.length) segments.push({
            count: holds.length, label: `${holds.length} Hold`,
            bg: "rgba(251, 191, 36, 0.12)", fg: "var(--color-warning)",
          });
          if (bears.length) segments.push({
            count: bears.length, label: `${bears.length} Bearish`,
            bg: "rgba(248, 113, 113, 0.15)", fg: "var(--color-error)",
          });
          return (
            <div style={{
              display: "flex", gap: 3, marginTop: "var(--space-md)", width: "100%",
            }}>
              {segments.map((seg) => (
                <div
                  key={seg.label}
                  style={{
                    flex: seg.count,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    padding: "5px 8px", borderRadius: 99,
                    background: seg.bg, color: seg.fg,
                    fontSize: 10, fontWeight: 700, letterSpacing: "0.03em",
                    whiteSpace: "nowrap", overflow: "hidden",
                    minWidth: 0,
                  }}
                >
                  {seg.label}
                </div>
              ))}
            </div>
          );
        })()}

        {/* Row 6: Signal pills */}
        <div style={{
          display: "flex", gap: "var(--space-xs)", marginTop: "var(--space-sm)",
          flexWrap: "wrap", alignItems: "center",
        }}>
          {/* Fills Gap badge — highlights stocks in underweight risk categories */}
          {(() => {
            const riskCat = SECTOR_RISK_MAP[rec.sector] ?? "mixed";
            const fillsGap = underweightCategories?.includes(riskCat);
            if (!fillsGap) return null;
            const catLabel = riskCat.charAt(0).toUpperCase() + riskCat.slice(1);
            return (
              <SignalPill
                label={`Fills ${catLabel} gap`}
                bg="rgba(99, 102, 241, 0.15)"
                fg="var(--color-accent-bright)"
              />
            );
          })()}
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
          {rec.dataSourceCount != null && rec.dataSourceTotal != null && (() => {
            const ratio = rec.dataSourceCount / rec.dataSourceTotal;
            const fg = ratio >= 0.83 ? "var(--color-success)" : ratio >= 0.58 ? "var(--color-warning)" : "var(--color-error)";
            const bg = ratio >= 0.83 ? "rgba(52, 211, 153, 0.08)" : ratio >= 0.58 ? "rgba(251, 191, 36, 0.10)" : "rgba(248, 113, 113, 0.10)";
            return <SignalPill label={`${rec.dataSourceCount}/${rec.dataSourceTotal} data`} bg={bg} fg={fg} />;
          })()}
        </div>

        {/* Advisory Board summary strip */}
        {(rec.boardNarrative?.headline || (rec.advisoryOpinions && rec.advisoryOpinions.length > 0)) && (() => {
          const opinions = rec.advisoryOpinions || [];
          const approveCount = opinions.filter((o) => o.vote === "APPROVE" || o.vote === "ENDORSE").length;
          const vetoCount = opinions.filter((o) => o.vote === "VETO").length;
          const total = opinions.length;
          const adjustedDiffers = rec.boardAdjustedVerdict && rec.boardAdjustedVerdict !== rec.verdict;

          let voteBg = "rgba(148, 163, 184, 0.12)";
          let voteFg = "var(--color-text-muted)";
          if (total > 0) {
            if (vetoCount > 0) {
              voteBg = "rgba(248, 113, 113, 0.12)";
              voteFg = "var(--color-error)";
            } else if (approveCount >= total * 0.75) {
              voteBg = "rgba(52, 211, 153, 0.12)";
              voteFg = "var(--color-success)";
            } else {
              voteBg = "rgba(251, 191, 36, 0.12)";
              voteFg = "var(--color-warning)";
            }
          }

          return (
            <div style={{
              marginTop: "var(--space-sm)",
              display: "flex", alignItems: "center", gap: "var(--space-sm)", flexWrap: "wrap",
            }}>
              {rec.boardNarrative?.headline && (
                <span style={{
                  flex: 1, minWidth: 0,
                  fontSize: "var(--text-xs)", color: "var(--color-text-secondary)",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  fontStyle: "italic",
                }}>
                  {rec.boardNarrative.headline}
                </span>
              )}
              {total > 0 && (
                <SignalPill
                  label={vetoCount > 0 ? `Board: ${vetoCount} Veto` : `Board: ${approveCount}/${total} Approve`}
                  bg={voteBg}
                  fg={voteFg}
                />
              )}
              {adjustedDiffers && (
                <SignalPill
                  label={`Board: ${rec.boardAdjustedVerdict}`}
                  bg="rgba(251, 191, 36, 0.15)"
                  fg="var(--color-warning)"
                />
              )}
            </div>
          );
        })()}

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
              {(rec.heldPosition.pnlPct ?? 0) >= 0 ? "+" : ""}{(rec.heldPosition.pnlPct ?? 0).toFixed(1)}%
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
              display: "flex", flexDirection: "column", gap: "var(--space-md)",
            }}>
              {/* Agent consensus panel — ring + avatar tiles */}
              {stances.length > 0 && (
                <AgentConsensusPanel
                  stances={stances}
                  consensusScore={rec.consensusScore ?? null}
                />
              )}

              {/* Signal tag cloud — frequency-weighted */}
              {stances.length > 0 && (
                <SignalTagCloud stances={stances} />
              )}

              {/* Agent price targets (from prediction card) */}
              {pc && pc.agentTargets && pc.agentTargets.length > 0 && (
                <div>
                  <div style={{
                    display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: "var(--space-xs)",
                  }}>
                    <Target size={12} color="var(--color-text-muted)" />
                    <span style={{
                      fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                      letterSpacing: "0.05em", color: "var(--color-text-muted)",
                    }}>
                      Agent Price Targets
                    </span>
                  </div>
                  <div style={{
                    display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
                    gap: "var(--space-xs)",
                  }}>
                    {[...pc.agentTargets]
                      .sort((a, b) => b.weight - a.weight)
                      .map((t) => (
                        <div
                          key={t.agent}
                          style={{
                            display: "flex", alignItems: "center", gap: "var(--space-xs)",
                            padding: "3px var(--space-sm)",
                            background: "var(--color-surface-0)",
                            borderRadius: "var(--radius-sm)",
                            border: "1px solid var(--glass-border)",
                          }}
                        >
                          <span style={{
                            fontSize: 10, fontWeight: 600, color: "var(--color-text-secondary)",
                            flex: 1, textTransform: "capitalize",
                          }}>
                            {t.agent}
                          </span>
                          <span style={{
                            fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 700,
                            color: t.targetPrice > pc.currentPrice ? "var(--color-success)" : "var(--color-error)",
                          }}>
                            {fmtPrice(t.targetPrice)}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* Risk summary from board narrative */}
              {rec.boardNarrative?.risk_summary && (
                <div style={{
                  padding: "var(--space-sm) var(--space-md)",
                  background: "rgba(248, 113, 113, 0.04)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid rgba(248, 113, 113, 0.1)",
                }}>
                  <div style={{
                    display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: 4,
                  }}>
                    <Shield size={12} color="var(--color-error)" />
                    <span style={{ fontSize: 10, fontWeight: 700, color: "var(--color-error)" }}>
                      Risk Summary
                    </span>
                  </div>
                  <FormattedProse text={rec.boardNarrative.risk_summary} fontSize="11px" color="var(--color-text-muted)" />
                </div>
              )}

              {/* Kill scenarios from adversarial result */}
              {adv && adv.kill_scenarios && adv.kill_scenarios.length > 0 && (
                <div>
                  <div style={{
                    display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: "var(--space-xs)",
                  }}>
                    <AlertTriangle size={12} color="var(--color-warning)" />
                    <span style={{
                      fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                      letterSpacing: "0.05em", color: "var(--color-warning)",
                    }}>
                      Kill Scenarios
                    </span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
                    {adv.kill_scenarios.slice(0, 3).map((ks, i) => {
                      const impactColor = ks.impact === "fatal" ? "var(--color-error)"
                        : ks.impact === "severe" ? "var(--color-warning)" : "var(--color-text-muted)";
                      return (
                        <div key={i} style={{
                          padding: "var(--space-xs) var(--space-sm)",
                          background: "var(--color-surface-0)",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--glass-border)",
                          fontSize: 10, color: "var(--color-text-secondary)",
                          display: "flex", alignItems: "flex-start", gap: "var(--space-sm)",
                        }}>
                          <span style={{
                            fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 4,
                            background: ks.likelihood === "high" ? "rgba(248, 113, 113, 0.12)"
                              : ks.likelihood === "medium" ? "rgba(251, 191, 36, 0.12)"
                              : "rgba(148, 163, 184, 0.08)",
                            color: ks.likelihood === "high" ? "var(--color-error)"
                              : ks.likelihood === "medium" ? "var(--color-warning)"
                              : "var(--color-text-muted)",
                            whiteSpace: "nowrap", flexShrink: 0,
                          }}>
                            {ks.likelihood}
                          </span>
                          <span style={{ flex: 1, lineHeight: 1.4 }}>{ks.scenario}</span>
                          <span style={{
                            fontSize: 9, fontWeight: 600, color: impactColor,
                            whiteSpace: "nowrap", flexShrink: 0,
                          }}>
                            {ks.impact}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Advisory board compact votes */}
              {rec.advisoryOpinions && rec.advisoryOpinions.length > 0 && (() => {
                const opinions = rec.advisoryOpinions!;
                const approves = opinions.filter((o) => o.vote === "APPROVE" || o.vote === "ENDORSE");
                const vetoes = opinions.filter((o) => o.vote === "VETO");
                return (
                  <div style={{
                    display: "flex", alignItems: "center", gap: "var(--space-sm)",
                    flexWrap: "wrap",
                  }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700,
                      color: vetoes.length > 0 ? "var(--color-error)" : "var(--color-success)",
                    }}>
                      Board: {approves.length} approve{vetoes.length > 0 ? `, ${vetoes.length} veto` : ""}
                    </span>
                    {opinions.map((o) => (
                      <span key={o.advisor_name} style={{
                        fontSize: 9, padding: "1px 6px", borderRadius: 4,
                        fontWeight: 600,
                        background: o.vote === "VETO"
                          ? "rgba(248, 113, 113, 0.12)"
                          : "rgba(52, 211, 153, 0.08)",
                        color: o.vote === "VETO"
                          ? "var(--color-error)"
                          : "var(--color-text-muted)",
                        border: `1px solid ${o.vote === "VETO" ? "rgba(248, 113, 113, 0.2)" : "var(--glass-border)"}`,
                      }}>
                        {o.display_name} {o.vote === "VETO" ? "\u2717" : "\u2713"}
                        {o.key_concern ? ` \u2014 ${o.key_concern}` : ""}
                      </span>
                    ))}
                  </div>
                );
              })()}

              {/* Portfolio fit — compact */}
              {rec.portfolioFit && (rec.portfolioFit as any).reasoning && (
                <div style={{
                  padding: "var(--space-sm) var(--space-md)",
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
                  <div style={{ marginTop: 4 }}>
                    <FormattedProse text={(rec.portfolioFit as any).reasoning} fontSize="11px" color="var(--color-text-muted)" />
                  </div>
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
  const { groupedByVerdict, totalCount, loading, error, refetch, portfolioGaps, allocationGuidance } = useRecommendations();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const [portfolioTarget, setPortfolioTarget] = useState<Recommendation | null>(null);
  const [addStatus, setAddStatus] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState("default");

  const handleRefresh = useCallback(async () => {
    await refetch();
  }, [refetch]);

  const { containerRef, pullDistance, refreshing } = usePullToRefresh({
    onRefresh: handleRefresh,
  });

  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader />
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
        <ViewHeader />
        <BentoCard>
          <p style={{ color: "var(--color-error)" }}>Failed to load: {error}</p>
        </BentoCard>
      </div>
    );
  }

  const verdictOrder = Object.keys(groupedByVerdict);

  return (
    <div ref={containerRef} style={{ height: "100%", overflowY: "auto" }}>
      {/* Pull-to-refresh indicator */}
      {(pullDistance > 0 || refreshing) && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          height: pullDistance, overflow: "hidden",
          transition: refreshing ? "height 0.2s ease" : "none",
        }}>
          <RefreshCw
            size={18}
            style={{
              color: "var(--color-text-muted)",
              opacity: Math.min(pullDistance / 60, 1),
              transform: `rotate(${pullDistance * 3}deg)`,
              animation: refreshing ? "spin 0.8s linear infinite" : "none",
            }}
          />
        </div>
      )}
      <ViewHeader
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

        {/* Verdict group badges + Sort controls */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
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

          {/* Sort bar */}
          <div style={{
            display: "flex", alignItems: "center", gap: "var(--space-xs)",
            fontSize: 10, color: "var(--color-text-muted)",
          }}>
            <span style={{ fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", marginRight: 2 }}>
              Sort
            </span>
            {SORT_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setSortKey(opt.key)}
                style={{
                  padding: "2px 10px", borderRadius: 99,
                  background: sortKey === opt.key ? "var(--color-accent-ghost)" : "transparent",
                  border: sortKey === opt.key ? "1px solid rgba(99,102,241,0.2)" : "1px solid transparent",
                  color: sortKey === opt.key ? "var(--color-accent-bright)" : "var(--color-text-muted)",
                  cursor: "pointer", fontSize: 10, fontWeight: 600,
                  fontFamily: "var(--font-sans)",
                  transition: "all 0.15s ease",
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Portfolio health strip — 3-tier allocation guidance */}
        <PortfolioHealthStrip gaps={portfolioGaps} guidance={allocationGuidance} />

        {/* Empty state */}
        {totalCount === 0 && (
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            gap: "var(--space-lg)", padding: "var(--space-2xl) var(--space-xl)",
            textAlign: "center",
          }}>
            <div style={{
              width: 64, height: 64, borderRadius: "50%",
              background: "var(--color-surface-1)", border: "1px solid var(--glass-border)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Rocket size={28} color="var(--color-text-muted)" strokeWidth={1.5} />
            </div>
            <div>
              <p style={{ margin: 0, fontSize: "var(--text-base)", fontWeight: 600, color: "var(--color-text-secondary)" }}>
                No recommendations yet
              </p>
              <p style={{ margin: "var(--space-sm) 0 0", fontSize: "var(--text-xs)", color: "var(--color-text-muted)", lineHeight: 1.5 }}>
                Run analysis on stocks from the Screener — those with actionable verdicts will appear here.
              </p>
            </div>
          </div>
        )}

        {/* Verdict groups */}
        {verdictOrder.map((v) => {
          const recs = sortRecs(groupedByVerdict[v], sortKey);
          return (
            <div key={v} id={`verdict-${v}`}>
              {/* Group wrapper — border container for whole category */}
              {(() => {
                const meta = verdictGroupMeta[v];
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
                    {/* Header — centered title, count on right */}
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      padding: "14px 12px",
                    }}>
                      <div style={{ flex: 1, textAlign: "center" }}>
                        <div style={{
                          fontSize: 13, fontWeight: 500,
                          color: vCol,
                          letterSpacing: "0.06em",
                          textTransform: "uppercase",
                        }}>
                          {meta?.title || verdictLabel[v] || v}
                        </div>
                        <div style={{
                          fontSize: 11, color: "var(--color-text-muted)",
                          marginTop: 3, fontWeight: 400,
                        }}>
                          {meta?.tagline || ""}
                        </div>
                      </div>
                      <span style={{
                        fontSize: 12, fontWeight: 700, color: vCol,
                        fontFamily: "var(--font-mono)",
                        opacity: 0.7,
                        flexShrink: 0,
                      }}>
                        {recs.length}
                      </span>
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
                      underweightCategories={portfolioGaps?.underweightCategories}
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
