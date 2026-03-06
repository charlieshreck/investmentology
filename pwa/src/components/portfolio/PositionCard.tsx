import { useState, useRef, useLayoutEffect } from "react";
import { motion, useMotionValue, animate } from "framer-motion";
import { formatCurrency, formatPct, pnlColor } from "../../utils/format";
import { PositionSparkline } from "../charts/PositionSparkline";
import type { Position } from "../../types/models";

export function PositionCard({
  position: p,
  onClick,
  onClose: _onClose,
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

  const [page, setPage] = useState(0);
  const dataX = useMotionValue(-9999);
  const containerRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

  useLayoutEffect(() => {
    if (!initialized.current && containerRef.current) {
      const w = containerRef.current.offsetWidth;
      dataX.set(-w);
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
        {/* Fixed left: Ticker + name + type badge */}
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
              {p.name.split(",")[0].replace(/\s*(?:Common\s+(?:Stock|Units?|Shares?)|Ordinary\s+Shares?|Inc\.?|Corp\.?|Ltd\.?|L\.?P\.?)\s*/gi, " ").trim()}
            </div>
          )}
          <div style={{ fontSize: 9, color: "var(--color-text-muted)", fontWeight: 500, marginTop: 1 }}>
            {p.shares}sh · {(p.weight ?? 0).toFixed(1)}%
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
              <div style={{ flex: 1, minWidth: 40 }}>
                <PositionSparkline ticker={p.ticker} entryDate={p.entryDate} avgCost={p.avgCost} />
              </div>

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
                { label: "Avg Cost", value: `$${(p.avgCost ?? 0).toFixed(2)}` },
                { label: "Basis", value: formatCurrency(costBasis) },
                { label: "P&L $", value: formatCurrency(p.unrealizedPnl), color: pnlColor(p.unrealizedPnl) },
                { label: "Shares", value: p.shares.toLocaleString() },
                { label: "Weight", value: `${(p.weight ?? 0).toFixed(1)}%` },
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
