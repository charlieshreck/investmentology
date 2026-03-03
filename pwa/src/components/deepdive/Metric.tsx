export function Metric({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>{label}</div>
      <div style={{ fontWeight: 600, fontFamily: mono ? "var(--font-mono)" : "inherit" }}>{value}</div>
    </div>
  );
}
