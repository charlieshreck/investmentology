import { formatCurrency } from "../../utils/format";

export function DividendCard({ position: p }: { position: any }) {
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
