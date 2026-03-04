import { useState } from "react";
import { motion } from "framer-motion";
import { formatCurrency, formatPct, pnlColor } from "../../utils/format";
import type { Position } from "../../types/models";

export function ClosePositionModal({
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
