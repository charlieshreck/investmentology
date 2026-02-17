/**
 * Soft-band balance bar: shows a value's position within green/amber/red zones.
 * No hard enforcement — just visual guidance.
 */

interface BalanceBarProps {
  label: string;
  pct: number;
  softMax: number;   // green → amber boundary
  warnMax: number;   // amber → red boundary
  color?: string;
  showIdealRange?: { min: number; max: number };
}

export function BalanceBar({ label, pct, softMax, warnMax, color, showIdealRange }: BalanceBarProps) {
  const zone = pct <= softMax ? "green" : pct <= warnMax ? "amber" : "red";
  const zoneColor =
    zone === "green" ? "var(--color-success)" :
    zone === "amber" ? "var(--color-warning)" :
    "var(--color-error)";

  // Scale: bar represents 0-60% (enough to show most allocations)
  const scale = 60;
  const barWidth = Math.min((pct / scale) * 100, 100);
  const softLine = (softMax / scale) * 100;
  const warnLine = (warnMax / scale) * 100;

  return (
    <div style={{ marginBottom: "var(--space-md)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: "var(--text-xs)", fontWeight: 500 }}>
          {label}
        </span>
        <span style={{
          fontSize: "var(--text-xs)",
          fontFamily: "var(--font-mono)",
          fontWeight: 600,
          color: zoneColor,
        }}>
          {pct.toFixed(1)}%
        </span>
      </div>

      <div style={{
        position: "relative",
        height: 8,
        background: "var(--color-surface-0)",
        borderRadius: "var(--radius-full)",
        overflow: "visible",
      }}>
        {/* Ideal range indicator (subtle background band) */}
        {showIdealRange && (
          <div style={{
            position: "absolute",
            left: `${(showIdealRange.min / scale) * 100}%`,
            width: `${((showIdealRange.max - showIdealRange.min) / scale) * 100}%`,
            height: "100%",
            background: "rgba(52, 211, 153, 0.12)",
            borderRadius: "var(--radius-full)",
          }} />
        )}

        {/* Value bar */}
        <div style={{
          position: "absolute",
          left: 0,
          top: 0,
          height: "100%",
          width: `${barWidth}%`,
          background: color ?? zoneColor,
          borderRadius: "var(--radius-full)",
          opacity: zone === "green" ? 0.8 : 1,
          transition: "width var(--duration-normal) var(--ease-out)",
        }} />

        {/* Soft max marker */}
        <div style={{
          position: "absolute",
          left: `${softLine}%`,
          top: -2,
          width: 1,
          height: 12,
          background: "var(--color-warning)",
          opacity: 0.5,
        }} />

        {/* Warn max marker */}
        {warnLine <= 100 && (
          <div style={{
            position: "absolute",
            left: `${warnLine}%`,
            top: -2,
            width: 1,
            height: 12,
            background: "var(--color-error)",
            opacity: 0.5,
          }} />
        )}
      </div>
    </div>
  );
}


interface RiskSpectrumProps {
  categories: Array<{
    name: string;
    pct: number;
    zone: string;
    idealMin: number;
    idealMax: number;
    warnMax: number;
  }>;
}

const RISK_COLORS: Record<string, string> = {
  growth: "#818cf8",
  cyclical: "#fbbf24",
  defensive: "#34d399",
  mixed: "#60a5fa",
  income: "#2dd4bf",
};

const RISK_LABELS: Record<string, string> = {
  growth: "Growth",
  cyclical: "Cyclical",
  defensive: "Defensive",
  mixed: "Mixed",
  income: "Income",
};

export function RiskSpectrum({ categories }: RiskSpectrumProps) {
  // Stacked bar showing the risk spectrum
  const active = categories.filter((c) => c.pct > 0);

  return (
    <div>
      {/* Stacked bar */}
      <div style={{
        display: "flex",
        height: 24,
        borderRadius: "var(--radius-sm)",
        overflow: "hidden",
        marginBottom: "var(--space-md)",
      }}>
        {active.map((c) => (
          <div
            key={c.name}
            title={`${RISK_LABELS[c.name] ?? c.name}: ${c.pct.toFixed(1)}%`}
            style={{
              width: `${c.pct}%`,
              background: RISK_COLORS[c.name] ?? "#94a3b8",
              opacity: c.zone === "green" ? 0.85 : c.zone === "amber" ? 0.95 : 1,
              transition: "width var(--duration-normal) var(--ease-out)",
              minWidth: c.pct > 0 ? 2 : 0,
            }}
          />
        ))}
      </div>

      {/* Legend */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-md)" }}>
        {active.map((c) => {
          const zoneColor =
            c.zone === "green" ? "var(--color-text-secondary)" :
            c.zone === "amber" ? "var(--color-warning)" :
            "var(--color-error)";

          return (
            <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{
                width: 8, height: 8, borderRadius: "var(--radius-full)",
                background: RISK_COLORS[c.name] ?? "#94a3b8",
              }} />
              <span style={{ fontSize: "var(--text-xs)", color: zoneColor }}>
                {RISK_LABELS[c.name] ?? c.name} {c.pct.toFixed(0)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
