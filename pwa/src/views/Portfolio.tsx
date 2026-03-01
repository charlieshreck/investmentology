import { useState, useEffect, useRef, useCallback, useLayoutEffect } from "react";
import { motion, AnimatePresence, useScroll, useTransform, useMotionValue, animate } from "framer-motion";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { AnimatedNumber } from "../components/shared/AnimatedNumber";
import { FloatingBar } from "../components/shared/FloatingBar";
import { SegmentedControl } from "../components/shared/SegmentedControl";
import { MetricCardSkeleton, PositionRowSkeleton } from "../components/shared/SkeletonCard";
import { BalanceBar } from "../components/shared/BalanceBar";
import { MarketStatus } from "../components/shared/MarketStatus";
import { CorrelationHeatmap } from "../components/charts/CorrelationHeatmap";
import { usePortfolio } from "../hooks/usePortfolio";
import { useCorrelations } from "../hooks/useCorrelations";
import { useConfetti } from "../hooks/useConfetti";
import { useWebSocket } from "../hooks/useWebSocket";
import { useAnalysis } from "../contexts/AnalysisContext";
import type { Position, Alert, ClosedPosition } from "../types/models";
import { useStore } from "../stores/useStore";
import {
  TrendingUp, TrendingDown, DollarSign, Wallet,
  ChevronDown, ChevronUp, Zap, AlertTriangle, BarChart3,
  Gauge, ShieldAlert, ArrowUpRight, ArrowDownRight, Sparkles,
} from "lucide-react";

function formatCurrency(n: number): string {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function formatPct(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function pnlColor(n: number): string {
  if (n > 0) return "var(--color-success)";
  if (n < 0) return "var(--color-error)";
  return "var(--color-text-secondary)";
}

function pnlGradientClass(n: number): string {
  if (n > 0) return "text-gradient-success";
  if (n < 0) return "text-gradient-error";
  return "";
}

function alertVariant(severity: Alert["severity"]): "accent" | "success" | "warning" | "error" | "neutral" {
  const map: Record<string, "accent" | "success" | "warning" | "error" | "neutral"> = {
    info: "accent", warning: "warning", error: "error", critical: "error",
  };
  return map[severity] ?? "neutral";
}

interface BalanceData {
  sectors: Array<{ name: string; pct: number; zone: string; color: string; softMax: number; warnMax: number; tickers: string[] }>;
  riskCategories: Array<{ name: string; pct: number; zone: string; idealMin: number; idealMax: number; warnMax: number }>;
  positionCount: number;
  sectorCount: number;
  health: string;
  insights: string[];
}

function usePortfolioBalance(positionCount: number) {
  const [balance, setBalance] = useState<BalanceData | null>(null);
  useEffect(() => {
    if (positionCount === 0) { setBalance(null); return; }
    fetch("/api/invest/portfolio/balance")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => setBalance(data))
      .catch(() => setBalance(null));
  }, [positionCount]);
  return balance;
}

/* ── Collapsible Section ── */
function Section({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  count,
}: {
  title: string;
  icon?: typeof TrendingUp;
  children: React.ReactNode;
  defaultOpen?: boolean;
  count?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [expanded, setExpanded] = useState(defaultOpen);
  return (
    <div>
      <button
        onClick={() => { setOpen((v) => !v); setExpanded(false); }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-sm)",
          width: "100%",
          padding: "var(--space-md) 0",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--color-text-secondary)",
          fontSize: "var(--text-sm)",
          fontWeight: 600,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        {Icon && <Icon size={14} strokeWidth={2} />}
        <span>{title}</span>
        {count != null && (
          <span style={{
            fontSize: "var(--text-2xs)",
            background: "var(--color-surface-2)",
            padding: "1px 8px",
            borderRadius: "var(--radius-full)",
            color: "var(--color-text-muted)",
            fontWeight: 500,
          }}>
            {count}
          </span>
        )}
        <span style={{ marginLeft: "auto" }}>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            onAnimationComplete={() => setExpanded(true)}
            style={{ overflow: expanded ? "visible" : "hidden" }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Mini Sparkline (since purchase) ── */
function PositionSparkline({ ticker, entryDate, avgCost }: { ticker: string; entryDate?: string; avgCost: number }) {
  const [points, setPoints] = useState<number[] | null>(null);

  useEffect(() => {
    // Calculate period from entry date
    let period = "3mo";
    if (entryDate) {
      const days = Math.floor((Date.now() - new Date(entryDate).getTime()) / 86400000);
      if (days > 365) period = "2y";
      else if (days > 180) period = "1y";
      else if (days > 90) period = "6mo";
      else period = "3mo";
    }
    fetch(`/api/invest/stock/${ticker}/chart?period=${period}`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.data?.length > 1) {
          setPoints(data.data.map((d: any) => d.close as number));
        }
      })
      .catch(() => {});
  }, [ticker, entryDate]);

  if (!points || points.length < 2) return null;

  const w = 80, h = 28;
  const min = Math.min(...points, avgCost);
  const max = Math.max(...points, avgCost);
  const range = max - min || 1;

  const toY = (v: number) => h - 2 - ((v - min) / range) * (h - 4);
  const toX = (i: number) => (i / (points.length - 1)) * w;

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p).toFixed(1)}`).join(" ");

  // Color based on chart trend (first vs last data point)
  const trend = points[points.length - 1] >= points[0];
  const lineColor = trend ? "var(--color-success)" : "var(--color-error)";
  const fillColor = trend ? "rgba(52,211,153,0.12)" : "rgba(248,113,113,0.12)";

  // Area fill
  const areaD = `${pathD} L${w},${h} L0,${h} Z`;

  // Avg cost reference line
  const costY = toY(avgCost);

  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display: "block" }}>
      {/* Area fill */}
      <path d={areaD} fill={fillColor} />
      {/* Avg cost dashed line */}
      <line x1={0} y1={costY} x2={w} y2={costY}
        stroke="var(--color-text-muted)" strokeWidth={0.5} strokeDasharray="2,2" opacity={0.4} />
      {/* Price line */}
      <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      {/* End dot */}
      <circle cx={w} cy={toY(points[points.length - 1])} r={2} fill={lineColor} />
    </svg>
  );
}

/* ── Position Card with swipe-to-reveal detail ── */
function PositionCard({
  position: p,
  onClick,
  onClose,
}: {
  position: Position & { dayChange?: number; dayChangePct?: number };
  onClick: () => void;
  onClose: () => void;
}) {
  const isPositive = p.unrealizedPnl >= 0;
  const accentColor = isPositive ? "var(--color-success)" : "var(--color-error)";
  const accentGlow = isPositive ? "rgba(52,211,153,0.06)" : "rgba(248,113,113,0.06)";
  const costBasis = p.avgCost * p.shares;
  const daysHeld = p.entryDate ? Math.floor((Date.now() - new Date(p.entryDate).getTime()) / 86400000) : null;

  const [page, setPage] = useState(0); // -1 = extra data, 0 = chart (default), 1 = detail metrics
  const dataX = useMotionValue(-9999); // offscreen until measured
  const containerRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

  // Center on page 0 (middle) before paint
  useLayoutEffect(() => {
    if (!initialized.current && containerRef.current) {
      const w = containerRef.current.offsetWidth;
      dataX.set(-w); // page 0 = -(0+1)*w
      initialized.current = true;
    }
  });

  const snapTo = (target: number) => {
    const w = containerRef.current?.offsetWidth ?? 200;
    animate(dataX, -(target + 1) * w, { type: "spring", stiffness: 200, damping: 26 });
    setPage(target);
  };

  return (
    <div
      style={{
        borderRadius: "var(--radius-md)",
        background: "var(--color-surface-0)",
        border: "1px solid var(--glass-border)",
        boxShadow: "var(--shadow-card), inset 0 1px 0 rgba(255,255,255,0.02)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Left accent bar */}
      <div style={{
        position: "absolute", left: 0, top: "15%", bottom: "15%",
        width: 3, borderRadius: "0 3px 3px 0",
        background: accentColor, opacity: 0.7,
        boxShadow: `0 0 8px ${accentGlow}`,
        zIndex: 3,
      }} />
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: "25%",
        background: `linear-gradient(90deg, ${accentGlow}, transparent)`,
        pointerEvents: "none", zIndex: 1,
      }} />

      <div style={{
        display: "flex",
        alignItems: "center",
        padding: "var(--space-md) var(--space-lg)",
        gap: "var(--space-md)",
      }}>
        {/* Fixed left: Ticker + name + type badge — always visible */}
        <div
          onClick={onClick}
          style={{ flexShrink: 0, paddingLeft: "var(--space-xs)", cursor: "pointer" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ fontWeight: 700, fontSize: "var(--text-sm)", letterSpacing: "0.02em" }}>
              {p.ticker}
            </span>
            {p.positionType && (
              <span style={{
                fontSize: 7,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                padding: "1px 5px",
                borderRadius: 4,
                background: p.positionType === "core"
                  ? "rgba(52,211,153,0.15)"
                  : p.positionType === "speculative"
                    ? "rgba(251,191,36,0.15)"
                    : "rgba(96,165,250,0.15)",
                color: p.positionType === "core"
                  ? "var(--color-success)"
                  : p.positionType === "speculative"
                    ? "var(--color-warning)"
                    : "var(--color-accent)",
                lineHeight: 1.4,
              }}>
                {p.positionType}
              </span>
            )}
          </div>
          {p.name && (
            <div style={{
              fontSize: 8, color: "var(--color-text-muted)", fontWeight: 500, marginTop: 1,
              whiteSpace: "nowrap",
            }}>
              {p.name.replace(/\s*Common Stock/i, "").trim()}
            </div>
          )}
          <div style={{ fontSize: 9, color: "var(--color-text-muted)", fontWeight: 500, marginTop: 1 }}>
            {p.shares}sh · {p.weight.toFixed(1)}%
          </div>
        </div>

        {/* Sliding data area — 3 pages */}
        <div
          ref={containerRef}
          style={{
            flex: 1,
            overflow: "hidden",
            position: "relative",
            minHeight: 40,
          }}
        >
          <motion.div
            drag="x"
            dragConstraints={containerRef}
            dragElastic={0.2}
            style={{ x: dataX, display: "flex", width: "300%", touchAction: "pan-y" }}
            onDragEnd={(_, info) => {
              const threshold = 40;
              const velThreshold = 150;
              if (info.offset.x < -threshold || info.velocity.x < -velThreshold) {
                snapTo(Math.min(page + 1, 1));
              } else if (info.offset.x > threshold || info.velocity.x > velThreshold) {
                snapTo(Math.max(page - 1, -1));
              } else {
                snapTo(page);
              }
            }}
          >
            {/* Page -1: Extra data (swipe right to reveal) */}
            <div style={{
              width: "33.333%",
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "2px 10px",
              alignContent: "center",
            }}>
              {[
                { label: "Value", value: formatCurrency(p.marketValue) },
                { label: "Type", value: p.positionType ? p.positionType.charAt(0).toUpperCase() + p.positionType.slice(1) : "—" },
                { label: "Held", value: daysHeld != null ? `${daysHeld}d` : "—" },
                { label: "Day P&L", value: p.dayChange != null ? formatCurrency(p.dayChange) : "—", color: pnlColor(p.dayChange ?? 0) },
              ].map((m) => (
                <div key={m.label} style={{ textAlign: "center" }}>
                  <div style={{
                    fontSize: 8, color: "var(--color-text-muted)",
                    textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700,
                  }}>{m.label}</div>
                  <div style={{
                    fontSize: 11, fontFamily: "var(--font-mono)", fontWeight: 700,
                    color: m.color || "var(--color-text)", lineHeight: 1.4,
                  }}>{m.value}</div>
                </div>
              ))}
            </div>

            {/* Page 0: Sparkline + P&L since purchase + Price (default view) */}
            <div style={{
              width: "33.333%",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              {/* Sparkline — fills available space */}
              <div style={{ flex: 1, minWidth: 40 }}>
                <PositionSparkline ticker={p.ticker} entryDate={p.entryDate} avgCost={p.avgCost} />
              </div>

              {/* P&L since purchase */}
              <div style={{ flexShrink: 0, textAlign: "center", minWidth: 48 }}>
                <div style={{
                  fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700,
                  color: pnlColor(p.unrealizedPnl),
                }}>
                  {formatPct(p.unrealizedPnlPct)}
                </div>
                <div style={{
                  fontSize: 8, color: "var(--color-text-muted)", fontWeight: 600,
                  textTransform: "uppercase", letterSpacing: "0.04em", marginTop: 1,
                }}>
                  since buy
                </div>
              </div>

              {/* Price + day change — right aligned */}
              <div style={{ textAlign: "right", flexShrink: 0, marginLeft: "auto" }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: 600 }}>
                  ${p.currentPrice?.toFixed(2) ?? "—"}
                </div>
                <div style={{
                  fontFamily: "var(--font-mono)", fontSize: 9, fontWeight: 600,
                  color: pnlColor(p.dayChangePct ?? 0), marginTop: 1,
                }}>
                  {p.dayChangePct != null ? `${formatPct(p.dayChangePct)} today` : ""}
                </div>
              </div>
            </div>

            {/* Page 1: Detail metrics (swipe left to reveal) */}
            <div style={{
              width: "33.333%",
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: "2px 8px",
              alignContent: "center",
            }}>
              {[
                { label: "Avg Cost", value: `$${p.avgCost.toFixed(2)}` },
                { label: "Basis", value: formatCurrency(costBasis) },
                { label: "P&L $", value: formatCurrency(p.unrealizedPnl), color: pnlColor(p.unrealizedPnl) },
                { label: "Shares", value: p.shares.toLocaleString() },
                { label: "Weight", value: `${p.weight.toFixed(1)}%` },
                { label: daysHeld != null ? "Held" : "Type", value: daysHeld != null ? `${daysHeld}d` : (p.positionType || "—") },
              ].map((m) => (
                <div key={m.label} style={{ textAlign: "center" }}>
                  <div style={{
                    fontSize: 8, color: "var(--color-text-muted)",
                    textTransform: "uppercase", letterSpacing: "0.04em",
                    fontWeight: 700,
                  }}>
                    {m.label}
                  </div>
                  <div style={{
                    fontSize: 11,
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                    color: m.color || "var(--color-text)",
                    lineHeight: 1.4,
                  }}>
                    {m.value}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

      </div>
    </div>
  );
}

/* ── Dividend Card (compact per-position) ── */
function DividendCard({ position: p }: { position: any }) {
  const yieldPct = p.dividendYield ?? 0;
  const monthly = p.monthlyDividend ?? 0;
  const annual = p.annualDividend ?? 0;
  if (annual <= 0) return null;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "var(--space-md)",
      padding: "var(--space-md) var(--space-lg)",
      background: "var(--color-surface-0)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--glass-border)",
      position: "relative",
      overflow: "hidden",
    }}>
      {/* Green accent */}
      <div style={{
        position: "absolute", left: 0, top: "15%", bottom: "15%",
        width: 3, borderRadius: "0 3px 3px 0",
        background: "var(--color-success)", opacity: 0.6,
      }} />

      <div style={{ flex: 1, paddingLeft: "var(--space-xs)" }}>
        <div style={{ fontWeight: 700, fontSize: "var(--text-sm)" }}>{p.ticker}</div>
        <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: 2 }}>
          {p.shares} shares · ${p.currentPrice?.toFixed(2)}
        </div>
      </div>

      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>Yield</div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-success)" }}>
          {yieldPct.toFixed(1)}%
        </div>
      </div>

      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>Monthly</div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-success)" }}>
          {formatCurrency(monthly)}
        </div>
      </div>

      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>Annual</div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-success)" }}>
          {formatCurrency(annual)}
        </div>
      </div>
    </div>
  );
}

/* ── Action Item Row with expandable reasoning ── */
function ActionItemRow({ action: a, index: i, color, bgColor, Icon, label, setOverlayTicker }: {
  action: { ticker: string; action: string; category: string };
  index: number; color: string; bgColor: string;
  Icon: React.ComponentType<{ size: number; color: string }>;
  label: string;
  setOverlayTicker: (t: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [reasoning, setReasoning] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchReasoning = () => {
    if (reasoning !== null || loading) return;
    setLoading(true);
    fetch(`/api/invest/stock/${a.ticker}`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          const verdict = data.verdict;
          const reason = verdict?.reasoning || verdict?.summary || verdict?.thesis || data.briefing?.summary || a.action;
          setReasoning(reason);
        } else {
          setReasoning(a.action);
        }
      })
      .catch(() => setReasoning(a.action))
      .finally(() => setLoading(false));
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.15 + i * 0.06 }}
      style={{ borderRadius: "var(--radius-md)", overflow: "hidden" }}
    >
      {/* Main row */}
      <div
        onClick={() => { setExpanded((v) => !v); fetchReasoning(); }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-sm)",
          padding: "10px var(--space-md)",
          background: bgColor,
          cursor: "pointer",
          borderRadius: expanded ? "var(--radius-md) var(--radius-md) 0 0" : "var(--radius-md)",
          transition: "border-radius 0.15s ease",
        }}
      >
        {/* Left accent bar */}
        <div style={{
          width: 3, height: 28, borderRadius: 2,
          background: color, flexShrink: 0, opacity: 0.8,
        }} />

        {/* Icon */}
        <div style={{
          width: 28, height: 28, borderRadius: "var(--radius-sm)",
          background: "rgba(0,0,0,0.15)", display: "flex",
          alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <Icon size={14} color={color} />
        </div>

        {/* Ticker + label */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{
              fontWeight: 800, fontSize: "var(--text-sm)",
              fontFamily: "var(--font-mono)", color: "var(--color-text)",
            }}>
              {a.ticker}
            </span>
            <span style={{
              fontSize: 9, fontWeight: 700,
              color, textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}>
              {label}
            </span>
          </div>
          <div style={{
            fontSize: "var(--text-xs)", color: "var(--color-text-secondary)",
            lineHeight: 1.3, marginTop: 1,
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {a.action}
          </div>
        </div>

        {/* Expand chevron */}
        <div style={{
          width: 22, height: 22, borderRadius: "var(--radius-full)",
          background: "rgba(255,255,255,0.05)", display: "flex",
          alignItems: "center", justifyContent: "center", flexShrink: 0,
          transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform 0.2s ease",
        }}>
          <ChevronDown size={12} color="var(--color-text-muted)" />
        </div>
      </div>

      {/* Expanded reasoning panel */}
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
              padding: "var(--space-md)",
              background: "var(--color-surface-1)",
              borderTop: `1px solid rgba(255,255,255,0.04)`,
              borderRadius: "0 0 var(--radius-md) var(--radius-md)",
            }}>
              {loading ? (
                <div className="skeleton" style={{ height: 40, borderRadius: "var(--radius-sm)" }} />
              ) : (
                <div style={{
                  fontSize: "var(--text-xs)", color: "var(--color-text-secondary)",
                  lineHeight: 1.6,
                }}>
                  {reasoning || a.action}
                </div>
              )}
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={(e) => { e.stopPropagation(); setOverlayTicker(a.ticker); }}
                style={{
                  marginTop: "var(--space-sm)",
                  padding: "6px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: `1px solid ${color}`,
                  background: "transparent",
                  color,
                  fontSize: 10,
                  fontWeight: 700,
                  fontFamily: "var(--font-sans)",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                Deep Dive →
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ── Closed Trade Card with "what could have been" ── */
function ClosedTradeCard({ trade: cp }: { trade: ClosedPosition }) {
  const [expanded, setExpanded] = useState(false);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const isWin = cp.realizedPnl >= 0;

  // Fetch current price when expanded
  useEffect(() => {
    if (!expanded || currentPrice !== null) return;
    fetch(`/api/invest/stock/${cp.ticker}`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        const price = data?.fundamentals?.price ?? data?.profile?.price ?? data?.profile?.currentPrice;
        if (price) setCurrentPrice(price);
      })
      .catch(() => {});
  }, [expanded, cp.ticker, currentPrice]);

  const exitP = cp.exitPrice ?? cp.entryPrice;
  const wouldBePnl = currentPrice != null ? (currentPrice - cp.entryPrice) * cp.shares : null;
  const wouldBePnlPct = currentPrice != null ? ((currentPrice - cp.entryPrice) / cp.entryPrice) * 100 : null;
  const missedGain = currentPrice != null ? (currentPrice - exitP) * cp.shares : null;

  return (
    <div style={{ borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      {/* Main row */}
      <motion.div
        whileTap={{ scale: 0.99 }}
        onClick={() => setExpanded((v) => !v)}
        style={{
          display: "flex", alignItems: "center", gap: "var(--space-md)",
          padding: "var(--space-md) var(--space-lg)",
          background: "var(--color-surface-0)",
          border: "1px solid var(--glass-border)",
          borderRadius: expanded ? "var(--radius-md) var(--radius-md) 0 0" : "var(--radius-md)",
          cursor: "pointer", position: "relative", overflow: "hidden",
        }}
      >
        <div style={{
          position: "absolute", left: 0, top: "15%", bottom: "15%", width: 3,
          borderRadius: "0 3px 3px 0", background: isWin ? "var(--color-success)" : "var(--color-error)", opacity: 0.6,
        }} />

        <div style={{ flex: 1, paddingLeft: "var(--space-xs)" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-xs)" }}>
            <span style={{ fontWeight: 700, fontSize: "var(--text-sm)" }}>{cp.ticker}</span>
            <span style={{ fontSize: 9, color: "var(--color-text-muted)" }}>
              {cp.holdingDays != null ? `${cp.holdingDays}d` : ""}
            </span>
          </div>
          <div style={{ fontSize: 10, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
            ${cp.entryPrice.toFixed(2)} → {cp.exitPrice != null ? `$${cp.exitPrice.toFixed(2)}` : "—"}
          </div>
        </div>

        <div style={{ textAlign: "right" }}>
          <div style={{
            fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 700,
            color: pnlColor(cp.realizedPnl),
          }}>
            {formatPct(cp.realizedPnlPct)}
          </div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: pnlColor(cp.realizedPnl), marginTop: 1 }}>
            {formatCurrency(cp.realizedPnl)}
          </div>
        </div>

        <div style={{
          width: 24, height: 24, borderRadius: "var(--radius-full)",
          background: "var(--color-surface-2)", display: "flex",
          alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </div>
      </motion.div>

      {/* What could have been panel */}
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
              padding: "var(--space-md) var(--space-lg)",
              background: "var(--color-surface-1)",
              borderRadius: "0 0 var(--radius-md) var(--radius-md)",
              border: "1px solid var(--glass-border)",
              borderTop: "none",
            }}>
              <div style={{
                fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase",
                letterSpacing: "0.08em", fontWeight: 600, marginBottom: 8,
              }}>
                What Could Have Been
              </div>

              {currentPrice === null ? (
                <div className="skeleton" style={{ height: 40, borderRadius: "var(--radius-sm)" }} />
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 1, background: "var(--glass-border)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
                  {[
                    { label: "Now", value: `$${currentPrice.toFixed(2)}`, color: "var(--color-text)" },
                    { label: "If Held", value: wouldBePnl != null ? formatCurrency(wouldBePnl) : "—", color: wouldBePnl != null ? pnlColor(wouldBePnl) : "var(--color-text-muted)" },
                    { label: missedGain != null && missedGain > 0 ? "Missed" : "Saved", value: missedGain != null ? formatCurrency(Math.abs(missedGain)) : "—", color: missedGain != null ? (missedGain > 0 ? "var(--color-warning)" : "var(--color-success)") : "var(--color-text-muted)" },
                  ].map((m) => (
                    <div key={m.label} style={{ padding: "8px 10px", background: "var(--color-surface-1)", textAlign: "center" }}>
                      <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2, fontWeight: 600 }}>{m.label}</div>
                      <div style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", fontWeight: 700, color: m.color }}>{m.value}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Visual comparison bar */}
              {currentPrice != null && wouldBePnlPct != null && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 9, color: "var(--color-text-muted)" }}>Sold at {formatPct(cp.realizedPnlPct)}</span>
                    <span style={{ fontSize: 9, color: pnlColor(wouldBePnlPct) }}>If held: {formatPct(wouldBePnlPct)}</span>
                  </div>
                  <div style={{ position: "relative", height: 6, background: "var(--color-surface-2)", borderRadius: "var(--radius-full)", overflow: "hidden" }}>
                    {/* Realized bar */}
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(Math.max((cp.realizedPnlPct + 50) / 100 * 100, 5), 95)}%` }}
                      transition={{ delay: 0.2, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                      style={{
                        position: "absolute", left: 0, top: 0, height: "100%",
                        background: isWin ? "var(--color-success)" : "var(--color-error)",
                        borderRadius: "var(--radius-full)", opacity: 0.7,
                      }}
                    />
                    {/* Current price marker */}
                    <div style={{
                      position: "absolute",
                      left: `${Math.min(Math.max((wouldBePnlPct + 50) / 100 * 100, 2), 98)}%`,
                      top: -2, width: 2, height: 10,
                      background: pnlColor(wouldBePnlPct),
                      borderRadius: 1,
                    }} />
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Close Position Modal ── */
function ClosePositionModal({
  position,
  onClose,
  onSubmit,
}: {
  position: Position;
  onClose: () => void;
  onSubmit: (positionId: number, exitPrice: number) => void;
}) {
  const [exitPrice, setExitPrice] = useState((position.currentPrice ?? position.avgCost).toString());
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.7)",
        backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "var(--space-xl)",
      }}
    >
      <motion.div
        initial={{ scale: 0.95, y: 10 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.95, y: 10 }}
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-surface-1)",
          borderRadius: "var(--radius-xl)",
          padding: "var(--space-2xl)",
          width: "100%",
          maxWidth: 380,
          border: "1px solid var(--glass-border)",
          boxShadow: "var(--shadow-elevated)",
          display: "flex", flexDirection: "column", gap: "var(--space-lg)",
        }}
      >
        <div style={{ fontSize: "var(--text-xl)", fontWeight: 700 }}>
          Close {position.ticker}
        </div>
        <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
          {position.shares} shares @ avg {formatCurrency(position.avgCost)}
        </div>
        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
          Exit Price
          <input
            type="number"
            step="0.01"
            value={exitPrice}
            onChange={(e) => setExitPrice(e.target.value)}
            style={{
              width: "100%", marginTop: 6,
              padding: "var(--space-md) var(--space-lg)",
              background: "var(--color-surface-0)",
              border: "1px solid var(--glass-border-light)",
              borderRadius: "var(--radius-md)",
              color: "var(--color-text-primary)",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--text-lg)",
              outline: "none",
              transition: "border-color 0.15s ease",
            }}
            onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(99,102,241,0.4)"; }}
            onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "var(--glass-border-light)"; }}
          />
        </label>
        {(() => {
          const ep = parseFloat(exitPrice);
          if (!isNaN(ep) && ep > 0) {
            const pnl = (ep - position.avgCost) * position.shares;
            const pnlPct = ((ep - position.avgCost) / position.avgCost) * 100;
            return (
              <div style={{
                fontSize: "var(--text-lg)",
                fontFamily: "var(--font-mono)",
                fontWeight: 600,
                color: pnlColor(pnl),
                textAlign: "center",
                padding: "var(--space-md)",
                background: pnl >= 0 ? "var(--color-success-glow)" : "var(--color-error-glow)",
                borderRadius: "var(--radius-md)",
              }}>
                {formatCurrency(pnl)} ({formatPct(pnlPct)})
              </div>
            );
          }
          return null;
        })()}
        <div style={{ display: "flex", gap: "var(--space-md)", marginTop: "var(--space-sm)" }}>
          <button
            onClick={onClose}
            style={{
              flex: 1, padding: "var(--space-md)",
              background: "var(--color-surface-0)",
              border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-md)",
              color: "var(--color-text-secondary)",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "var(--text-sm)",
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => {
              const ep = parseFloat(exitPrice);
              if (ep > 0 && position.id != null) onSubmit(position.id, ep);
            }}
            style={{
              flex: 1, padding: "var(--space-md)",
              background: "linear-gradient(135deg, #ef4444, #f87171)",
              border: "none",
              borderRadius: "var(--radius-md)",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 700,
              fontSize: "var(--text-sm)",
            }}
          >
            Close Position
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

interface AdvisorCard {
  type: string;
  ticker: string;
  title: string;
  detail: string;
  reasoning: string;
  priority: string;
}

interface BriefingSummary {
  date: string;
  pendulumLabel: string;
  pendulumScore: number;
  positionCount: number;
  totalValue: number;
  totalUnrealizedPnl: number;
  newRecommendationCount: number;
  alertCount: number;
  overallRiskLevel: string;
  topActions: Array<{ category: string; ticker: string; action: string }>;
}

export function Portfolio() {
  const {
    positions, totalValue, dayPnl, dayPnlPct, cash, alerts,
    closedPositions, totalRealizedPnl,
    loading, error, closePosition,
  } = usePortfolio();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const performance = useStore((s) => s.performance);
  const { startAnalysis, isRunning: analysisRunning } = useAnalysis();
  const [closeTarget, setCloseTarget] = useState<Position | null>(null);
  const [closeStatus, setCloseStatus] = useState<string | null>(null);
  const [advisorCards, setAdvisorCards] = useState<AdvisorCard[]>([]);
  const [briefing, setBriefing] = useState<BriefingSummary | null>(null);
  const [corrOpen, setCorrOpen] = useState(false);
  const [posFilter, setPosFilter] = useState("all");
  const balance = usePortfolioBalance(positions.length);
  const scrollRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const [showFloatingBar, setShowFloatingBar] = useState(false);

  useEffect(() => {
    if (positions.length === 0) return;
    fetch("/api/invest/portfolio/advisor")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data?.actions) setAdvisorCards(data.actions); })
      .catch(() => {});
  }, [positions.length]);

  useEffect(() => {
    if (positions.length === 0) return;
    fetch("/api/invest/daily/briefing/summary")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data?.date) setBriefing(data); })
      .catch(() => {});
  }, [positions.length]);

  const tickerFingerprint = positions.map((p) => p.ticker).sort().join(",");
  const { data: corrData } = useCorrelations(positions.length, tickerFingerprint);
  const { fire } = useConfetti();
  const { status: wsStatus, prices: livePrices } = useWebSocket({ enabled: positions.length > 0 });
  const prevPnlSign = useRef<number | null>(null);

  const totalPnlForConfetti = positions.reduce((s, p) => s + p.unrealizedPnl, 0);
  useEffect(() => {
    if (!loading && positions.length > 0) {
      const sign = totalPnlForConfetti > 0 ? 1 : totalPnlForConfetti < 0 ? -1 : 0;
      if (prevPnlSign.current !== null && prevPnlSign.current <= 0 && sign > 0) {
        fire("profit", "portfolio-positive");
      }
      prevPnlSign.current = sign;
    }
  }, [totalPnlForConfetti, loading, positions.length, fire]);

  // Show floating bar when hero scrolls out of view
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handler = () => {
      const heroBottom = heroRef.current?.getBoundingClientRect().bottom ?? 999;
      setShowFloatingBar(heroBottom < 0);
    };
    el.addEventListener("scroll", handler, { passive: true });
    return () => el.removeEventListener("scroll", handler);
  }, []);

  const handleClose = async (positionId: number, exitPrice: number) => {
    try {
      await closePosition(positionId, exitPrice);
      setCloseStatus("Position closed");
      setCloseTarget(null);
      setTimeout(() => setCloseStatus(null), 3000);
    } catch (err) {
      setCloseStatus(`Error: ${err instanceof Error ? err.message : "failed"}`);
      setTimeout(() => setCloseStatus(null), 3000);
    }
  };

  const fmtCurrencyStable = useCallback((n: number) => formatCurrency(n), []);
  const fmtPctStable = useCallback((n: number) => formatPct(n), []);

  /* ── Loading skeleton ── */
  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Portfolio" />
        <div style={{ padding: "var(--space-xl)", display: "flex", flexDirection: "column", gap: "var(--space-xl)" }}>
          <div className="skeleton" style={{ height: 140, borderRadius: "var(--radius-xl)" }} />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
            <MetricCardSkeleton />
            <MetricCardSkeleton />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            <PositionRowSkeleton />
            <PositionRowSkeleton />
            <PositionRowSkeleton />
            <PositionRowSkeleton />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "var(--space-xl)", paddingTop: "calc(var(--header-height) + var(--space-xl))" }}>
        <ViewHeader title="Portfolio" />
        <BentoCard>
          <p style={{ color: "var(--color-error)" }}>Failed to load portfolio: {error}</p>
        </BentoCard>
      </div>
    );
  }

  // Merge live WebSocket prices
  const enrichedPositions = positions.map((p) => {
    const live = livePrices[p.ticker];
    if (!live) return p;
    const livePrice = live.price;
    const mv = livePrice * p.shares;
    const cost = p.avgCost * p.shares;
    const pnl = mv - cost;
    const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
    return {
      ...p,
      currentPrice: livePrice,
      marketValue: mv,
      unrealizedPnl: pnl,
      unrealizedPnlPct: pnlPct,
      dayChange: live.change * p.shares,
      dayChangePct: live.changePct,
    };
  });

  const totalPnl = enrichedPositions.reduce((s, p) => s + p.unrealizedPnl, 0);
  const enrichedTotalValue = enrichedPositions.reduce((s, p) => s + p.marketValue, 0) + cash;
  const totalPnlPct = enrichedTotalValue > 0 ? (totalPnl / (enrichedTotalValue - totalPnl - cash)) * 100 : 0;
  const cashPct = enrichedTotalValue > 0 ? (cash / enrichedTotalValue) * 100 : 0;
  const enrichedDayPnl = enrichedPositions.reduce((s, p) => s + (p.dayChange || 0), 0);
  const liveDayPnl = Object.keys(livePrices).length > 0 ? enrichedDayPnl : dayPnl;
  const liveDayPnlPct = Object.keys(livePrices).length > 0 && enrichedTotalValue > 0
    ? (enrichedDayPnl / (enrichedTotalValue - enrichedDayPnl)) * 100
    : dayPnlPct;

  // Filter positions
  const winnersCount = enrichedPositions.filter(p => p.unrealizedPnl > 0).length;
  const losersCount = enrichedPositions.filter(p => p.unrealizedPnl < 0).length;
  const dividendPositions = enrichedPositions.filter((p: any) => (p.annualDividend ?? 0) > 0);
  const totalMonthlyDiv = enrichedPositions.reduce((s: number, p: any) => s + (p.monthlyDividend || 0), 0);
  const totalAnnualDiv = enrichedPositions.reduce((s: number, p: any) => s + (p.annualDividend || 0), 0);
  const filteredPositions = posFilter === "all" ? enrichedPositions
    : posFilter === "winners" ? enrichedPositions.filter(p => p.unrealizedPnl > 0)
    : posFilter === "losers" ? enrichedPositions.filter(p => p.unrealizedPnl <= 0)
    : []; // dividends handled separately

  return (
    <div ref={scrollRef} style={{ height: "100%", overflowY: "auto" }}>
      {/* Floating portfolio summary bar */}
      <FloatingBar
        visible={showFloatingBar}
        totalValue={formatCurrency(enrichedTotalValue || totalValue)}
        dayPnl={liveDayPnl}
        dayPnlFormatted={`${formatCurrency(liveDayPnl)} (${formatPct(liveDayPnlPct)})`}
        positionCount={positions.length}
      />

      <ViewHeader
        title="Portfolio"
        subtitle={`${positions.length} positions`}
        right={
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
            {positions.length > 0 && (
              <button
                onClick={() => { if (!analysisRunning) startAnalysis(positions.map((p) => p.ticker)); }}
                disabled={analysisRunning}
                style={{
                  padding: "8px 16px",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  background: analysisRunning ? "var(--color-surface-2)" : "var(--gradient-active)",
                  color: analysisRunning ? "var(--color-text-muted)" : "#fff",
                  border: "none",
                  borderRadius: "var(--radius-full)",
                  cursor: analysisRunning ? "not-allowed" : "pointer",
                  whiteSpace: "nowrap",
                  letterSpacing: "0.02em",
                }}
              >
                {analysisRunning ? "Running..." : "Re-analyze All"}
              </button>
            )}
            <MarketStatus wsStatus={wsStatus} />
          </div>
        }
      />

      <div style={{ padding: "var(--space-xl)", display: "flex", flexDirection: "column", gap: "var(--space-xl)" }}>

        {/* ═══════ HERO: Total Value ═══════ */}
        <motion.div
          ref={heroRef}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          style={{
            padding: "var(--space-2xl) var(--space-xl)",
            background: "linear-gradient(135deg, var(--color-surface-0) 0%, rgba(99,102,241,0.08) 100%)",
            borderRadius: "var(--radius-xl)",
            border: "1px solid rgba(99,102,241,0.12)",
            boxShadow: "var(--shadow-card), 0 0 80px rgba(99,102,241,0.06), inset 0 1px 0 rgba(255,255,255,0.04)",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Decorative orb glows */}
          <div style={{
            position: "absolute",
            top: "-40%",
            left: "50%",
            transform: "translateX(-50%)",
            width: "120%",
            height: "100%",
            background: "radial-gradient(ellipse at center, rgba(99,102,241,0.10) 0%, transparent 60%)",
            pointerEvents: "none",
          }} />
          <div className="orb-glow" style={{
            top: "-20%",
            right: "-10%",
            width: "40%",
            height: "60%",
            background: "var(--color-accent-glow)",
          }} />
          <div className="orb-glow" style={{
            bottom: "-30%",
            left: "-5%",
            width: "35%",
            height: "50%",
            background: "var(--color-accent-ghost)",
          }} />

          <div style={{
            fontSize: "var(--text-xs)",
            fontWeight: 600,
            color: "var(--color-accent-bright)",
            textTransform: "uppercase",
            letterSpacing: "0.12em",
            marginBottom: "var(--space-md)",
            position: "relative",
          }}>
            Total Portfolio Value
          </div>

          <div style={{ position: "relative" }}>
            <AnimatedNumber
              value={enrichedTotalValue || totalValue}
              format={fmtCurrencyStable}
              className="text-gradient"
              style={{
                fontSize: "var(--text-4xl)",
                fontWeight: 800,
                fontFamily: "var(--font-mono)",
                letterSpacing: "-0.02em",
                lineHeight: 1.1,
              }}
            />
          </div>

          {/* Day P&L strip */}
          <div style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: "var(--space-md)",
            marginTop: "var(--space-lg)",
            position: "relative",
          }}>
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "var(--space-xs)",
              padding: "6px 16px",
              borderRadius: "var(--radius-full)",
              background: liveDayPnl >= 0 ? "var(--color-success-glow)" : "var(--color-error-glow)",
            }}>
              {liveDayPnl >= 0 ? <TrendingUp size={14} color="var(--color-success)" /> : <TrendingDown size={14} color="var(--color-error)" />}
              <AnimatedNumber
                value={liveDayPnl}
                format={fmtCurrencyStable}
                style={{
                  fontSize: "var(--text-sm)",
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  color: pnlColor(liveDayPnl),
                }}
              />
              <AnimatedNumber
                value={liveDayPnlPct}
                format={fmtPctStable}
                style={{
                  fontSize: "var(--text-xs)",
                  fontFamily: "var(--font-mono)",
                  color: pnlColor(liveDayPnlPct),
                  opacity: 0.8,
                }}
              />
            </div>
          </div>
        </motion.div>

        {/* ═══════ Metric Cards ═══════ */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--space-md)",
        }}>
          <BentoCard title="Total P&L" delay={0.05} variant={totalPnl >= 0 ? "success" : "error"} compact glow>
            <AnimatedNumber
              value={totalPnl}
              format={fmtCurrencyStable}
              className={pnlGradientClass(totalPnl)}
              style={{ fontSize: "var(--text-2xl)", fontWeight: 800, fontFamily: "var(--font-mono)" }}
            />
            <AnimatedNumber
              value={totalPnlPct}
              format={fmtPctStable}
              style={{ fontSize: "var(--text-sm)", color: pnlColor(totalPnlPct), marginTop: 4 }}
            />
          </BentoCard>
          <BentoCard title="Cash" delay={0.1} compact>
            <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-sm)" }}>
              <Wallet size={16} color="var(--color-text-muted)" style={{ marginTop: 2 }} />
              <AnimatedNumber
                value={cash}
                format={fmtCurrencyStable}
                style={{ fontSize: "var(--text-2xl)", fontWeight: 800, fontFamily: "var(--font-mono)" }}
              />
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
              {cashPct.toFixed(1)}% of portfolio
            </div>
          </BentoCard>
        </div>

        {/* ═══════ Performance ═══════ */}
        {performance && (
          <Section title="Performance" icon={BarChart3}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: "var(--space-sm)" }}>
              {[
                { label: "Alpha", value: performance.alphaPct, fmt: (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`, color: performance.alphaPct != null ? pnlColor(performance.alphaPct) : undefined },
                { label: "Sharpe", value: performance.sharpeRatio, fmt: (v: number) => v.toFixed(2) },
                { label: "Sortino", value: performance.sortinoRatio, fmt: (v: number) => v.toFixed(2) },
                { label: "Win Rate", value: performance.winRate, fmt: (v: number) => `${(v * 100).toFixed(0)}%` },
                { label: "Max DD", value: performance.maxDrawdownPct, fmt: (v: number) => `${v.toFixed(1)}%`, color: "var(--color-error)" },
              ].map((m) => (
                <div
                  key={m.label}
                  style={{
                    padding: "var(--space-md) var(--space-lg)",
                    background: "var(--color-surface-0)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--glass-border)",
                  }}
                >
                  <div style={{ fontSize: "var(--text-2xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                    {m.label}
                  </div>
                  <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: m.color }}>
                    {m.value != null ? m.fmt(m.value) : "—"}
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* ═══════ Daily Intelligence ═══════ */}
        {briefing && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            style={{
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
              border: "1px solid var(--glass-border)",
              background: "var(--color-surface-0)",
            }}
          >
            {/* Header strip with gradient */}
            <div style={{
              padding: "var(--space-md) var(--space-lg)",
              background: "var(--gradient-surface)",
              borderBottom: "1px solid var(--glass-border)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
            }}>
              <Sparkles size={14} color="var(--color-accent-bright)" />
              <span style={{
                fontSize: "var(--text-xs)",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--color-accent-bright)",
              }}>
                Daily Intel
              </span>
              <span style={{
                fontSize: 9,
                color: "var(--color-text-muted)",
                fontFamily: "var(--font-mono)",
                marginLeft: "auto",
              }}>
                {new Date(briefing.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
              </span>
            </div>

            {/* Pendulum + Risk + Stats row */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 1,
              background: "var(--glass-border)",
            }}>
              {/* Pendulum gauge */}
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", textAlign: "center" }}>
                <div style={{ position: "relative", width: 48, height: 28, margin: "0 auto 4px" }}>
                  <svg viewBox="0 0 48 28" style={{ width: "100%", height: "100%", overflow: "visible" }}>
                    {/* Gauge track */}
                    <path d="M 4 26 A 20 20 0 0 1 44 26" fill="none" stroke="var(--color-surface-2)" strokeWidth="4" strokeLinecap="round" />
                    {/* Gauge fill — position based on pendulumScore (0=fear, 100=greed) */}
                    <path
                      d="M 4 26 A 20 20 0 0 1 44 26"
                      fill="none"
                      stroke={briefing.pendulumScore <= 30 ? "var(--color-success)" : briefing.pendulumScore <= 60 ? "var(--color-warning)" : "var(--color-error)"}
                      strokeWidth="4"
                      strokeLinecap="round"
                      strokeDasharray={`${(briefing.pendulumScore / 100) * 63} 63`}
                    />
                    {/* Needle */}
                    {(() => {
                      const angle = Math.PI - (briefing.pendulumScore / 100) * Math.PI;
                      const nx = 24 + 16 * Math.cos(angle);
                      const ny = 26 - 16 * Math.sin(angle);
                      return <circle cx={nx} cy={ny} r="2.5" fill="var(--color-text)" stroke="var(--color-surface-0)" strokeWidth="1" />;
                    })()}
                  </svg>
                </div>
                <div style={{
                  fontSize: "var(--text-xs)", fontWeight: 800, textTransform: "capitalize",
                  color: briefing.pendulumScore <= 30 ? "var(--color-success)" : briefing.pendulumScore <= 60 ? "var(--color-warning)" : "var(--color-error)",
                }}>
                  {briefing.pendulumLabel}
                </div>
                <div style={{ fontSize: 8, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
                  Sentiment
                </div>
              </div>

              {/* Risk level */}
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", textAlign: "center" }}>
                <motion.div
                  animate={{ scale: [1, 1.15, 1] }}
                  transition={{ repeat: Infinity, duration: 2.5, ease: "easeInOut" }}
                  style={{ marginBottom: 4 }}
                >
                  <ShieldAlert
                    size={22}
                    color={briefing.overallRiskLevel === "low" ? "var(--color-success)" : briefing.overallRiskLevel === "elevated" ? "var(--color-warning)" : "var(--color-error)"}
                    style={{ margin: "0 auto" }}
                  />
                </motion.div>
                <div style={{
                  fontSize: "var(--text-xs)", fontWeight: 800, textTransform: "capitalize",
                  color: briefing.overallRiskLevel === "low" ? "var(--color-success)" : briefing.overallRiskLevel === "elevated" ? "var(--color-warning)" : "var(--color-error)",
                }}>
                  {briefing.overallRiskLevel}
                </div>
                <div style={{ fontSize: 8, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
                  Risk Level
                </div>
              </div>

              {/* Alerts */}
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", textAlign: "center" }}>
                <div style={{
                  fontSize: "var(--text-xl)", fontWeight: 800, fontFamily: "var(--font-mono)",
                  color: briefing.alertCount > 0 ? "var(--color-warning)" : "var(--color-text-muted)",
                }}>
                  {briefing.alertCount}
                </div>
                <div style={{ fontSize: 8, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
                  {briefing.alertCount === 1 ? "Alert" : "Alerts"}
                </div>
              </div>
            </div>

            {/* Action Items */}
            {(() => {
              // Merge advisor API actions + briefing topActions
              const allActions = [
                ...advisorCards.map((c) => ({ ticker: c.ticker, action: c.reasoning || c.detail || c.title, category: c.type.toLowerCase() })),
                ...briefing.topActions.map((a) => ({ ticker: a.ticker, action: a.action, category: a.category })),
              ];
              const seen = new Set<string>();
              const actions = allActions.filter((a) => { if (seen.has(a.ticker)) return false; seen.add(a.ticker); return true; });

              if (actions.length === 0) return null;

              return (
                <div style={{ padding: "var(--space-md) var(--space-lg)", borderTop: "1px solid var(--glass-border)" }}>
                  <div style={{
                    fontSize: "var(--text-2xs)", color: "var(--color-text-secondary)", textTransform: "uppercase",
                    letterSpacing: "0.08em", fontWeight: 700, marginBottom: "var(--space-sm)",
                  }}>
                    Action Items
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {actions.slice(0, 5).map((a, i) => {
                      const isBuy = a.category === "buy" || a.category === "add_more" || a.category === "deploy_cash";
                      const isSell = a.category === "sell" || a.category === "trim";
                      const color = isBuy ? "var(--color-success)" : isSell ? "var(--color-error)" : "var(--color-accent-bright)";
                      const bgColor = isBuy ? "rgba(52,211,153,0.10)" : isSell ? "rgba(248,113,113,0.10)" : "rgba(99,102,241,0.08)";
                      const ActionIcon = isBuy ? ArrowUpRight : isSell ? ArrowDownRight : Zap;
                      const label = isBuy ? "BUY" : isSell ? "SELL" : "ACTION";

                      return <ActionItemRow key={a.ticker + i} action={a} index={i} color={color} bgColor={bgColor} Icon={ActionIcon} label={label} setOverlayTicker={setOverlayTicker} />;
                    })}
                  </div>
                </div>
              );
            })()}

            {/* New recs badge strip */}
            {briefing.newRecommendationCount > 0 && (
              <div style={{
                padding: "8px var(--space-lg)",
                borderTop: "1px solid var(--glass-border)",
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                background: "rgba(99,102,241,0.04)",
              }}>
                <Sparkles size={12} color="var(--color-accent-bright)" />
                <span style={{ fontSize: 10, color: "var(--color-accent-bright)", fontWeight: 600 }}>
                  {briefing.newRecommendationCount} new recommendation{briefing.newRecommendationCount !== 1 ? "s" : ""} today
                </span>
              </div>
            )}
          </motion.div>
        )}

        {/* ═══════ Positions (with Dividends tab) ═══════ */}
        <Section title="Positions" icon={DollarSign} count={enrichedPositions.length} defaultOpen={true}>
          <div style={{ marginBottom: "var(--space-md)" }}>
            <SegmentedControl
              segments={[
                { id: "all", label: "All", count: enrichedPositions.length },
                { id: "winners", label: "Winners", count: winnersCount },
                { id: "losers", label: "Losers", count: losersCount },
                ...(totalAnnualDiv > 0 ? [{ id: "dividends", label: "Dividends", count: dividendPositions.length }] : []),
              ]}
              activeId={posFilter}
              onChange={setPosFilter}
            />
          </div>

          <AnimatePresence mode="wait">
            {posFilter === "dividends" ? (
              <motion.div
                key="dividends"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                {/* Dividend totals banner */}
                <div style={{
                  display: "flex",
                  gap: "var(--space-sm)",
                  marginBottom: "var(--space-md)",
                }}>
                  {[
                    { label: "Monthly", value: formatCurrency(totalMonthlyDiv) },
                    { label: "Annual", value: formatCurrency(totalAnnualDiv) },
                  ].map((m) => (
                    <div key={m.label} style={{
                      flex: 1,
                      padding: "var(--space-md)",
                      background: "rgba(52,211,153,0.06)",
                      border: "1px solid rgba(52,211,153,0.15)",
                      borderRadius: "var(--radius-md)",
                      textAlign: "center",
                    }}>
                      <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4, fontWeight: 600 }}>{m.label}</div>
                      <div className="text-gradient-success" style={{ fontSize: "var(--text-lg)", fontWeight: 800, fontFamily: "var(--font-mono)" }}>
                        {m.value}
                      </div>
                    </div>
                  ))}
                </div>
                {/* Dividend cards */}
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                  {dividendPositions.map((p: any, i: number) => (
                    <motion.div
                      key={p.ticker}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.04, duration: 0.3 }}
                    >
                      <DividendCard position={p} />
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div
                key={posFilter}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
              >
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-sm)",
                  perspective: 1200,
                  perspectiveOrigin: "center top",
                }}>
                  {filteredPositions.map((p, i) => (
                    <motion.div
                      key={p.ticker}
                      initial={{
                        opacity: 0,
                        rotateX: -70,
                        scaleY: 0.4,
                        y: -30 * Math.min(i, 6),
                      }}
                      animate={{
                        opacity: 1,
                        rotateX: 0,
                        scaleY: 1,
                        y: 0,
                      }}
                      transition={{
                        delay: 0.3 + i * 0.08,
                        duration: 0.55,
                        ease: [0.22, 1, 0.36, 1],
                      }}
                      style={{
                        transformOrigin: "top center",
                        transformStyle: "preserve-3d",
                      }}
                    >
                      <PositionCard
                        position={p}
                        onClick={() => setOverlayTicker(p.ticker)}
                        onClose={() => setCloseTarget(p)}
                      />
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </Section>

        {/* ═══════ Balance ═══════ */}
        {balance && balance.sectors.length > 0 && (
          <Section title="Balance" defaultOpen={false}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>

              {/* Exploded pie + health badge */}
              <div style={{
                position: "relative",
                padding: "var(--space-lg)",
                background: "var(--color-surface-0)",
                borderRadius: "var(--radius-lg)",
                border: "1px solid var(--glass-border)",
              }}>
                {/* Health badge top-right */}
                <div style={{ position: "absolute", top: 12, right: 12, zIndex: 2 }}>
                  <Badge
                    variant={balance.health === "excellent" || balance.health === "good" ? "success" : balance.health === "fair" ? "warning" : "error"}
                    size="lg"
                  >
                    {balance.health}
                  </Badge>
                </div>

                {/* 3D Pie chart centered */}
                <div style={{
                  display: "flex", justifyContent: "center", marginBottom: "var(--space-lg)",
                  perspective: 600,
                }}>
                  <motion.div
                    initial={{ rotateX: 0, scale: 0.9, opacity: 0 }}
                    animate={{ rotateX: 45, scale: 1, opacity: 1 }}
                    transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                    style={{
                      position: "relative", width: 200, height: 200,
                      transformStyle: "preserve-3d",
                    }}
                  >
                    {/* Drop shadow layer beneath the pie */}
                    <div style={{
                      position: "absolute", inset: "15%",
                      borderRadius: "50%",
                      background: "radial-gradient(ellipse, rgba(0,0,0,0.4) 0%, transparent 70%)",
                      transform: "translateZ(-8px) translateY(12px) scaleY(0.6)",
                      filter: "blur(8px)",
                    }} />

                    {/* Thickness / side ring — simulates 3D depth */}
                    <svg viewBox="0 0 100 100" style={{
                      position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible",
                      transform: "translateZ(-4px)",
                    }}>
                      {(() => {
                        const cx = 50, cy = 50, r = 40;
                        let startAngle = -90;
                        const SECTOR_COLORS: Record<string, string> = {
                          Technology: "#3b82f6", "Basic Materials": "#f59e0b", Utilities: "#10b981",
                          "Consumer Defensive": "#06b6d4", Healthcare: "#ec4899", "Financial Services": "#8b5cf6",
                          "Consumer Cyclical": "#f97316", Energy: "#ef4444", Industrials: "#64748b",
                          "Communication Services": "#14b8a6", "Real Estate": "#a855f7",
                        };
                        return balance.sectors.map((s, i) => {
                          const angle = (s.pct / 100) * 360;
                          const endAngle = startAngle + angle;
                          const midAngle = startAngle + angle / 2;
                          const midRad = (midAngle * Math.PI) / 180;
                          const color = SECTOR_COLORS[s.name] || s.color || `hsl(${i * 72}, 65%, 55%)`;
                          const zone = s.pct <= s.softMax ? "green" : s.pct <= s.warnMax ? "amber" : "red";
                          const explode = zone !== "green" ? 3.5 : 0.8;
                          const offsetX = Math.cos(midRad) * explode;
                          const offsetY = Math.sin(midRad) * explode;
                          const largeArc = angle > 180 ? 1 : 0;
                          const startRad = (startAngle * Math.PI) / 180;
                          const endRad = (endAngle * Math.PI) / 180;
                          const x1 = cx + offsetX + r * Math.cos(startRad);
                          const y1 = cy + offsetY + r * Math.sin(startRad);
                          const x2 = cx + offsetX + r * Math.cos(endRad);
                          const y2 = cy + offsetY + r * Math.sin(endRad);
                          const path = `M ${cx + offsetX} ${cy + offsetY} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;
                          startAngle = endAngle;
                          return (
                            <path
                              key={`rim-${s.name}`}
                              d={path}
                              fill={color}
                              opacity={0.3}
                              stroke="rgba(0,0,0,0.3)"
                              strokeWidth="0.5"
                            />
                          );
                        });
                      })()}
                      <circle cx="50" cy="50" r="20" fill="var(--color-surface-0)" opacity="0.5" />
                    </svg>

                    {/* Main pie face */}
                    <svg viewBox="0 0 100 100" style={{
                      position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible",
                      filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.3))",
                    }}>
                      <defs>
                        {/* Glossy highlight overlay */}
                        <radialGradient id="pie-gloss" cx="35%" cy="30%" r="60%">
                          <stop offset="0%" stopColor="rgba(255,255,255,0.25)" />
                          <stop offset="50%" stopColor="rgba(255,255,255,0.08)" />
                          <stop offset="100%" stopColor="rgba(0,0,0,0.15)" />
                        </radialGradient>
                        {/* Per-sector gradient defs generated inline */}
                        {balance.sectors.map((s, i) => {
                          const SECTOR_COLORS: Record<string, string> = {
                            Technology: "#3b82f6", "Basic Materials": "#f59e0b", Utilities: "#10b981",
                            "Consumer Defensive": "#06b6d4", Healthcare: "#ec4899", "Financial Services": "#8b5cf6",
                            "Consumer Cyclical": "#f97316", Energy: "#ef4444", Industrials: "#64748b",
                            "Communication Services": "#14b8a6", "Real Estate": "#a855f7",
                          };
                          const color = SECTOR_COLORS[s.name] || s.color || `hsl(${i * 72}, 65%, 55%)`;
                          return (
                            <linearGradient key={`grad-${i}`} id={`sector-grad-${i}`} x1="0%" y1="0%" x2="100%" y2="100%">
                              <stop offset="0%" stopColor={color} stopOpacity="1" />
                              <stop offset="45%" stopColor={color} stopOpacity="0.85" />
                              <stop offset="100%" stopColor={color} stopOpacity="0.6" />
                            </linearGradient>
                          );
                        })}
                        {/* Inner shadow ring */}
                        <radialGradient id="inner-shadow" cx="50%" cy="50%" r="50%">
                          <stop offset="70%" stopColor="transparent" />
                          <stop offset="100%" stopColor="rgba(0,0,0,0.15)" />
                        </radialGradient>
                      </defs>

                      {(() => {
                        const cx = 50, cy = 50, r = 40;
                        let startAngle = -90;
                        const SECTOR_COLORS: Record<string, string> = {
                          Technology: "#3b82f6", "Basic Materials": "#f59e0b", Utilities: "#10b981",
                          "Consumer Defensive": "#06b6d4", Healthcare: "#ec4899", "Financial Services": "#8b5cf6",
                          "Consumer Cyclical": "#f97316", Energy: "#ef4444", Industrials: "#64748b",
                          "Communication Services": "#14b8a6", "Real Estate": "#a855f7",
                        };

                        return balance.sectors.map((s, i) => {
                          const angle = (s.pct / 100) * 360;
                          const endAngle = startAngle + angle;
                          const midAngle = startAngle + angle / 2;
                          const midRad = (midAngle * Math.PI) / 180;
                          const color = SECTOR_COLORS[s.name] || s.color || `hsl(${i * 72}, 65%, 55%)`;
                          const zone = s.pct <= s.softMax ? "green" : s.pct <= s.warnMax ? "amber" : "red";

                          const explode = zone !== "green" ? 3.5 : 0.8;
                          const offsetX = Math.cos(midRad) * explode;
                          const offsetY = Math.sin(midRad) * explode;

                          const largeArc = angle > 180 ? 1 : 0;
                          const startRad = (startAngle * Math.PI) / 180;
                          const endRad = (endAngle * Math.PI) / 180;
                          const x1 = cx + offsetX + r * Math.cos(startRad);
                          const y1 = cy + offsetY + r * Math.sin(startRad);
                          const x2 = cx + offsetX + r * Math.cos(endRad);
                          const y2 = cy + offsetY + r * Math.sin(endRad);

                          const path = `M ${cx + offsetX} ${cy + offsetY} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;

                          startAngle = endAngle;

                          return (
                            <motion.path
                              key={s.name}
                              d={path}
                              fill={`url(#sector-grad-${i})`}
                              stroke="rgba(0,0,0,0.25)"
                              strokeWidth="0.6"
                              initial={{ scale: 0.6, opacity: 0 }}
                              animate={{ scale: 1, opacity: 1 }}
                              transition={{ delay: 0.1 + i * 0.08, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                              style={{ transformOrigin: `${cx + offsetX}px ${cy + offsetY}px` }}
                            />
                          );
                        });
                      })()}

                      {/* Glossy highlight over entire pie */}
                      <circle cx="50" cy="50" r="40" fill="url(#pie-gloss)" pointerEvents="none" />

                      {/* Subtle inner ring shadow */}
                      <circle cx="50" cy="50" r="40" fill="url(#inner-shadow)" pointerEvents="none" />

                      {/* Center hole — glossy center disc */}
                      <circle cx="50" cy="50" r="21" fill="rgba(0,0,0,0.15)" />
                      <circle cx="50" cy="50" r="20" fill="var(--color-surface-0)" />
                      <circle cx="50" cy="50" r="20" fill="url(#pie-gloss)" opacity="0.4" />

                      {/* Outer rim highlight — catches light on the top edge */}
                      <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />
                    </svg>

                    {/* Center text — on top of everything */}
                    <div style={{
                      position: "absolute", inset: 0,
                      display: "flex", flexDirection: "column",
                      alignItems: "center", justifyContent: "center",
                      transform: "translateZ(2px)",
                    }}>
                      <div style={{ fontSize: "var(--text-lg)", fontWeight: 800, fontFamily: "var(--font-mono)", textShadow: "0 1px 4px rgba(0,0,0,0.5)" }}>
                        {balance.sectorCount}
                      </div>
                      <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: -2, textShadow: "0 1px 2px rgba(0,0,0,0.4)" }}>sectors</div>
                    </div>
                  </motion.div>
                </div>

                {/* Sector legend cards */}
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {balance.sectors.map((s, i) => {
                    const zone = s.pct <= s.softMax ? "green" : s.pct <= s.warnMax ? "amber" : "red";
                    const SECTOR_COLORS: Record<string, string> = {
                      Technology: "#3b82f6", "Basic Materials": "#f59e0b", Utilities: "#10b981",
                      "Consumer Defensive": "#06b6d4", Healthcare: "#ec4899", "Financial Services": "#8b5cf6",
                      "Consumer Cyclical": "#f97316", Energy: "#ef4444", Industrials: "#64748b",
                      "Communication Services": "#14b8a6", "Real Estate": "#a855f7",
                    };
                    const color = SECTOR_COLORS[s.name] || s.color || `hsl(${i * 72}, 65%, 55%)`;
                    const borderColor = zone === "red" ? "rgba(248,113,113,0.4)" : zone === "amber" ? "rgba(251,191,36,0.3)" : "var(--glass-border)";
                    const bgGlow = zone === "red" ? "rgba(248,113,113,0.06)" : zone === "amber" ? "rgba(251,191,36,0.04)" : "transparent";

                    return (
                      <motion.div
                        key={s.name}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.2 + i * 0.06 }}
                        style={{
                          display: "flex", alignItems: "center", gap: "var(--space-sm)",
                          padding: "8px var(--space-md)",
                          borderRadius: "var(--radius-sm)",
                          background: bgGlow,
                          border: `1px solid ${borderColor}`,
                        }}
                      >
                        <div style={{ width: 12, height: 12, borderRadius: 3, background: color, flexShrink: 0 }} />
                        <span style={{ flex: 1, fontSize: "var(--text-xs)", fontWeight: 600 }}>{s.name}</span>
                        <span style={{ fontSize: 9, color: "var(--color-text-muted)" }}>{s.tickers?.join(", ")}</span>

                        {/* Proportion bar */}
                        <div style={{ width: 50, height: 6, background: "var(--color-surface-2)", borderRadius: 3, overflow: "hidden", flexShrink: 0 }}>
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(s.pct / 50 * 100, 100)}%` }}
                            transition={{ delay: 0.3 + i * 0.06, duration: 0.5 }}
                            style={{
                              height: "100%", borderRadius: 3,
                              background: zone === "red" ? "var(--color-error)" : zone === "amber" ? "var(--color-warning)" : color,
                            }}
                          />
                        </div>

                        <span style={{
                          fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", fontWeight: 700,
                          minWidth: 35, textAlign: "right",
                          color: zone === "red" ? "var(--color-error)" : zone === "amber" ? "var(--color-warning)" : "var(--color-text-secondary)",
                        }}>
                          {s.pct.toFixed(0)}%
                        </span>

                        {zone !== "green" && (
                          <span style={{
                            fontSize: 8, fontWeight: 700, textTransform: "uppercase",
                            padding: "2px 6px", borderRadius: "var(--radius-full)",
                            background: zone === "red" ? "rgba(248,113,113,0.15)" : "rgba(251,191,36,0.12)",
                            color: zone === "red" ? "var(--color-error)" : "var(--color-warning)",
                            letterSpacing: "0.04em", flexShrink: 0,
                          }}>
                            {zone === "red" ? "Over" : "Watch"}
                          </span>
                        )}
                      </motion.div>
                    );
                  })}
                </div>
              </div>


              {/* Insights */}
              {balance.insights.length > 0 && (
                <div style={{
                  padding: "var(--space-md) var(--space-lg)",
                  background: "var(--color-surface-0)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--glass-border)",
                  borderLeft: `3px solid ${
                    balance.health === "excellent" || balance.health === "good" ? "var(--color-success)" :
                    balance.health === "fair" ? "var(--color-warning)" : "var(--color-error)"
                  }`,
                }}>
                  {balance.insights.map((insight, i) => (
                    <div key={i} style={{
                      fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.6,
                      marginBottom: i < balance.insights.length - 1 ? 6 : 0,
                    }}>
                      {insight}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Section>
        )}

        {/* ═══════ Correlation ═══════ */}
        {corrData && corrData.tickers.length >= 2 && corrData.correlations.length > 0 && (
          <Section title="Correlation Matrix" defaultOpen={false}>
            <BentoCard>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-lg)" }}>
                90-day pairwise price correlations
              </div>
              <CorrelationHeatmap tickers={corrData.tickers} correlations={corrData.correlations} />
            </BentoCard>
          </Section>
        )}

        {/* ═══════ Alerts ═══════ */}
        {alerts.length > 0 && (
          <Section title="Alerts" icon={AlertTriangle} count={alerts.length}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {alerts.map((a) => (
                <div
                  key={a.id}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "var(--space-md)",
                    padding: "var(--space-lg)",
                    borderRadius: "var(--radius-md)",
                    background: "var(--color-surface-0)",
                    border: "1px solid var(--glass-border)",
                  }}
                >
                  <Badge variant={alertVariant(a.severity)}>{a.severity}</Badge>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>
                      {a.ticker && <span style={{ color: "var(--color-accent-bright)", marginRight: "var(--space-sm)" }}>{a.ticker}</span>}
                      {a.title}
                    </div>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4, lineHeight: 1.5 }}>
                      {a.message}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* ═══════ Closed Positions ═══════ */}
        {closedPositions.length > 0 && (
          <Section title="Closed Trades" defaultOpen={false} count={closedPositions.length}>
            {/* Total realized banner */}
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "var(--space-md) var(--space-lg)", marginBottom: "var(--space-sm)",
              background: "var(--color-surface-0)", borderRadius: "var(--radius-md)",
              border: "1px solid var(--glass-border)",
            }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {closedPositions.length} trade{closedPositions.length !== 1 ? "s" : ""} realized
              </span>
              <span style={{ fontSize: "var(--text-base)", fontFamily: "var(--font-mono)", fontWeight: 700, color: pnlColor(totalRealizedPnl) }}>
                {formatCurrency(totalRealizedPnl)}
              </span>
            </div>
            {/* Individual closed trade cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {closedPositions.map((cp) => (
                <ClosedTradeCard key={cp.id} trade={cp} />
              ))}
            </div>
          </Section>
        )}

        {/* Status toast */}
        <AnimatePresence>
          {closeStatus && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              style={{
                position: "fixed",
                bottom: "calc(var(--nav-height) + var(--space-lg))",
                left: "50%",
                transform: "translateX(-50%)",
                padding: "var(--space-md) var(--space-xl)",
                borderRadius: "var(--radius-full)",
                background: closeStatus.startsWith("Error") ? "var(--color-error)" : "var(--color-success)",
                color: "#fff",
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                boxShadow: "var(--shadow-elevated)",
                zIndex: 50,
              }}
            >
              {closeStatus}
            </motion.div>
          )}
        </AnimatePresence>

        <div style={{ height: "var(--nav-height)" }} />
      </div>

      {/* Close Position Modal */}
      <AnimatePresence>
        {closeTarget && (
          <ClosePositionModal
            position={closeTarget}
            onClose={() => setCloseTarget(null)}
            onSubmit={handleClose}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
