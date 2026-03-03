import { BentoCard } from "../shared/BentoCard";
import type { PositionData } from "../../views/StockDeepDive";

export function PositionTile({ position }: { position: PositionData }) {
  const pnlColor = position.pnl >= 0 ? "var(--color-success)" : "var(--color-error)";
  const daysHeld = position.entryDate
    ? Math.floor((Date.now() - new Date(position.entryDate).getTime()) / 86400000)
    : null;

  return (
    <BentoCard compact>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "var(--space-md)",
      }}>
        <div style={{
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
          fontWeight: 600,
        }}>
          {position.shares.toFixed(2)} shares
        </div>
        <div style={{
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
          fontSize: "var(--text-sm)",
          color: pnlColor,
        }}>
          {position.pnl >= 0 ? "+" : ""}${position.pnl.toFixed(2)}
          <span style={{ fontSize: "var(--text-xs)", marginLeft: 4 }}>
            ({position.pnlPct >= 0 ? "+" : ""}{position.pnlPct.toFixed(1)}%)
          </span>
        </div>
        {daysHeld != null && (
          <div style={{
            fontSize: "var(--text-xs)",
            color: "var(--color-text-muted)",
            fontFamily: "var(--font-mono)",
          }}>
            {daysHeld}d
          </div>
        )}
      </div>
    </BentoCard>
  );
}
