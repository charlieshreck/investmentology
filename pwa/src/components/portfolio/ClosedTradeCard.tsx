import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatCurrency, formatPct, pnlColor } from "../../utils/format";
import { apiFetch } from "../../utils/apiClient";
import type { ClosedPosition } from "../../types/models";

export function ClosedTradeCard({ trade: cp }: { trade: ClosedPosition }) {
  const [expanded, setExpanded] = useState(false);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const isWin = cp.realizedPnl >= 0;

  useEffect(() => {
    if (!expanded || currentPrice !== null) return;
    apiFetch<any>(`/stock/${cp.ticker}`)
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
