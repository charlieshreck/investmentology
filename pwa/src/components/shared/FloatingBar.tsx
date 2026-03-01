import { motion, AnimatePresence } from "framer-motion";
import { TrendingUp, TrendingDown } from "lucide-react";

interface FloatingBarProps {
  visible: boolean;
  totalValue: string;
  dayPnl: number;
  dayPnlFormatted: string;
  positionCount: number;
}

export function FloatingBar({ visible, totalValue, dayPnl, dayPnlFormatted, positionCount }: FloatingBarProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ y: -60, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -60, opacity: 0 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
          style={{
            position: "fixed",
            top: 0,
            left: "50%",
            transform: "translateX(-50%)",
            width: "100%",
            maxWidth: 520,
            zIndex: 55,
            padding: "0 var(--space-lg)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px var(--space-xl)",
              marginTop: "var(--space-sm)",
              background: "rgba(10, 10, 18, 0.92)",
              backdropFilter: "blur(24px) saturate(1.8)",
              WebkitBackdropFilter: "blur(24px) saturate(1.8)",
              borderRadius: "var(--radius-full)",
              border: "1px solid var(--glass-border-light)",
              boxShadow: "0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.03) inset, var(--shadow-glow-accent)",
            }}
          >
            {/* Value */}
            <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-sm)" }}>
              <span style={{
                fontSize: "var(--text-lg)",
                fontWeight: 800,
                fontFamily: "var(--font-mono)",
                color: "var(--color-text-primary)",
                letterSpacing: "-0.01em",
              }}>
                {totalValue}
              </span>
              <span style={{
                fontSize: "var(--text-2xs)",
                color: "var(--color-text-muted)",
                fontWeight: 500,
              }}>
                {positionCount} pos
              </span>
            </div>

            {/* Day P&L pill */}
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              padding: "4px 12px",
              borderRadius: "var(--radius-full)",
              background: dayPnl >= 0 ? "rgba(52,211,153,0.12)" : "rgba(248,113,113,0.12)",
              border: `1px solid ${dayPnl >= 0 ? "rgba(52,211,153,0.2)" : "rgba(248,113,113,0.2)"}`,
            }}>
              {dayPnl >= 0
                ? <TrendingUp size={12} color="var(--color-success)" />
                : <TrendingDown size={12} color="var(--color-error)" />
              }
              <span style={{
                fontSize: "var(--text-xs)",
                fontWeight: 700,
                fontFamily: "var(--font-mono)",
                color: dayPnl >= 0 ? "var(--color-success)" : "var(--color-error)",
              }}>
                {dayPnlFormatted}
              </span>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
