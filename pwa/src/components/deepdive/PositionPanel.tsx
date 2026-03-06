import { CollapsiblePanel } from "./CollapsiblePanel";
import { Metric } from "./Metric";
import { Badge } from "../shared/Badge";
import type { PositionData } from "../../views/StockDeepDive";

export function PositionPanel({ position, onSell }: {
  position: PositionData;
  onSell: () => void;
}) {
  const pnlColor = (position.pnl ?? 0) >= 0 ? "var(--color-success)" : "var(--color-error)";
  const daysHeld = position.entryDate
    ? Math.floor((Date.now() - new Date(position.entryDate).getTime()) / 86400000)
    : null;

  const preview = `${(position.shares ?? 0).toFixed(2)} shares | ${(position.pnl ?? 0) >= 0 ? "+" : ""}$${(position.pnl ?? 0).toFixed(2)} (${(position.pnlPct ?? 0) >= 0 ? "+" : ""}${(position.pnlPct ?? 0).toFixed(1)}%)`;

  return (
    <CollapsiblePanel
      title="Position Detail"
      preview={preview}
      badge={
        <Badge variant={position.positionType === "core" ? "success" : position.positionType === "speculative" ? "warning" : "accent"}>
          {position.positionType}
        </Badge>
      }
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "var(--space-md)" }}>
        <Metric label="Shares" value={(position.shares ?? 0).toFixed(2)} mono />
        <Metric label="Entry" value={`$${(position.entryPrice ?? 0).toFixed(2)}`} mono />
        <Metric label="Current" value={`$${(position.currentPrice ?? position.entryPrice ?? 0).toFixed(2)}`} mono />
        <Metric label="P&L" value={
          <span style={{ color: pnlColor }}>
            {(position.pnl ?? 0) >= 0 ? "+" : ""}${(position.pnl ?? 0).toFixed(2)} ({(position.pnlPct ?? 0) >= 0 ? "+" : ""}{(position.pnlPct ?? 0).toFixed(1)}%)
          </span>
        } />
        {position.weight != null && <Metric label="Weight" value={`${(position.weight * 100).toFixed(1)}%`} mono />}
        {daysHeld != null && <Metric label="Held" value={`${daysHeld}d`} mono />}
        {position.stopLoss != null && <Metric label="Stop Loss" value={`$${position.stopLoss.toFixed(2)}`} mono />}
        {position.fairValue != null && <Metric label="Fair Value" value={`$${position.fairValue.toFixed(2)}`} mono />}
      </div>

      <div style={{ marginTop: "var(--space-md)", display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={onSell}
          style={{
            padding: "var(--space-xs) var(--space-md)",
            borderRadius: "var(--radius-sm)",
            background: "var(--color-error)",
            border: "none",
            color: "#fff",
            cursor: "pointer",
            fontSize: "var(--text-xs)",
            fontWeight: 600,
          }}
        >
          Sell
        </button>
      </div>

      {position.thesis && (
        <div style={{
          marginTop: "var(--space-md)",
          fontSize: "var(--text-sm)",
          color: "var(--color-text-secondary)",
          lineHeight: 1.6,
          fontStyle: "italic",
          borderTop: "1px solid var(--glass-border)",
          paddingTop: "var(--space-md)",
        }}>
          {position.thesis}
        </div>
      )}
    </CollapsiblePanel>
  );
}
