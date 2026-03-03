export function FiftyTwoWeekBar({ low, high, current }: { low: number; high: number; current: number }) {
  const range = high - low;
  const pct = range > 0 ? Math.max(0, Math.min(100, ((current - low) / range) * 100)) : 50;
  return (
    <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-sm)" }}>52-Week Range</div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
        <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-error)" }}>${low.toFixed(0)}</span>
        <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--color-surface-2)", position: "relative" }}>
          <div style={{ position: "absolute", left: `${pct}%`, top: -2, width: 10, height: 10, borderRadius: "50%", background: "var(--color-accent-bright)", transform: "translateX(-50%)" }} />
        </div>
        <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-success)" }}>${high.toFixed(0)}</span>
      </div>
    </div>
  );
}
