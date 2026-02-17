interface FunnelStage {
  label: string;
  count: number;
}

interface FunnelChartProps {
  stages: FunnelStage[];
}

export function FunnelChart({ stages }: FunnelChartProps) {
  if (stages.length === 0) return null;

  const maxCount = stages[0].count;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-sm)",
      }}
    >
      {stages.map((stage, i) => {
        const widthPct = maxCount > 0 ? (stage.count / maxCount) * 100 : 0;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
            <div
              style={{
                flex: 1,
                position: "relative",
                height: 28,
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  height: "100%",
                  width: `${widthPct}%`,
                  background:
                    i === 0
                      ? "var(--color-surface-3)"
                      : `rgba(99, 102, 241, ${0.15 + (i / stages.length) * 0.5})`,
                  borderRadius: "var(--radius-sm)",
                  transition: `width var(--duration-slow) var(--ease-out)`,
                  display: "flex",
                  alignItems: "center",
                  paddingLeft: "var(--space-md)",
                }}
              >
                <span
                  style={{
                    fontSize: "var(--text-xs)",
                    color: "var(--color-text)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {stage.label}
                </span>
              </div>
            </div>
            <span
              style={{
                fontSize: "var(--text-sm)",
                fontFamily: "var(--font-mono)",
                color: "var(--color-text-secondary)",
                minWidth: 48,
                textAlign: "right",
              }}
            >
              {stage.count.toLocaleString()}
            </span>
          </div>
        );
      })}
    </div>
  );
}
