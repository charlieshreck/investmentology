import type { PredictionCard } from "../../types/models";

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export function PriceRangeBar({ card }: { card: PredictionCard }) {
  const { bearCase, currentPrice, compositeTarget, targetRangeHigh } = card;

  const points = [bearCase, currentPrice, compositeTarget, targetRangeHigh].filter(
    (v): v is number => v != null && v > 0,
  );
  if (points.length < 2) return null;

  const min = Math.min(...points) * 0.97;
  const max = Math.max(...points) * 1.03;
  const range = max - min;
  const pct = (v: number) => ((v - min) / range) * 100;

  const currentPct = pct(currentPrice);
  const targetPct = compositeTarget ? pct(compositeTarget) : null;
  const bearPct = bearCase ? pct(bearCase) : null;
  const highPct = targetRangeHigh ? pct(targetRangeHigh) : null;

  return (
    <div style={{ padding: "var(--space-sm) 0" }}>
      {/* Labels row */}
      <div style={{ position: "relative", height: 16, marginBottom: 4 }}>
        {bearCase != null && (
          <span style={{
            position: "absolute", left: `${bearPct}%`, transform: "translateX(-50%)",
            fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-error)", whiteSpace: "nowrap",
          }}>
            {fmtPrice(bearCase)}
          </span>
        )}
        <span style={{
          position: "absolute", left: `${currentPct}%`, transform: "translateX(-50%)",
          fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--color-text)", whiteSpace: "nowrap",
        }}>
          {fmtPrice(currentPrice)}
        </span>
        {compositeTarget != null && (
          <span style={{
            position: "absolute", left: `${targetPct}%`, transform: "translateX(-50%)",
            fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--color-success)", whiteSpace: "nowrap",
          }}>
            {fmtPrice(compositeTarget)}
          </span>
        )}
      </div>

      {/* Bar */}
      <div style={{
        position: "relative", height: 6, borderRadius: 3,
        background: "var(--color-surface-2)",
        overflow: "visible",
      }}>
        {/* Downside zone (bear → current) */}
        {bearCase != null && bearPct != null && (
          <div style={{
            position: "absolute",
            left: `${bearPct}%`,
            width: `${currentPct - bearPct}%`,
            height: "100%",
            background: "linear-gradient(90deg, rgba(248,113,113,0.4), rgba(248,113,113,0.15))",
            borderRadius: "3px 0 0 3px",
          }} />
        )}

        {/* Upside zone (current → target) */}
        {targetPct != null && (
          <div style={{
            position: "absolute",
            left: `${currentPct}%`,
            width: `${targetPct - currentPct}%`,
            height: "100%",
            background: "linear-gradient(90deg, rgba(52,211,153,0.15), rgba(52,211,153,0.4))",
            borderRadius: "0 3px 3px 0",
          }} />
        )}

        {/* Extended range (target → high) */}
        {highPct != null && targetPct != null && highPct > targetPct && (
          <div style={{
            position: "absolute",
            left: `${targetPct}%`,
            width: `${highPct - targetPct}%`,
            height: "100%",
            background: "rgba(52,211,153,0.08)",
          }} />
        )}

        {/* Bear marker */}
        {bearCase != null && bearPct != null && (
          <div style={{
            position: "absolute", left: `${bearPct}%`, top: -3,
            width: 2, height: 12,
            background: "var(--color-error)",
            borderRadius: 1,
            transform: "translateX(-50%)",
          }} />
        )}

        {/* Current price diamond */}
        <div style={{
          position: "absolute", left: `${currentPct}%`, top: -4,
          width: 14, height: 14,
          transform: "translateX(-50%) rotate(45deg)",
          background: "var(--color-surface-1)",
          border: "2px solid var(--color-text)",
          borderRadius: 2,
          zIndex: 2,
        }} />

        {/* Target marker */}
        {targetPct != null && (
          <div style={{
            position: "absolute", left: `${targetPct}%`, top: -4,
            width: 12, height: 12,
            borderRadius: "50%",
            background: "var(--color-success)",
            border: "2px solid var(--color-surface-1)",
            transform: "translateX(-50%)",
            zIndex: 1,
          }} />
        )}

        {/* High range marker */}
        {highPct != null && targetPct != null && highPct > targetPct + 1 && (
          <div style={{
            position: "absolute", left: `${highPct}%`, top: -2,
            width: 2, height: 10,
            background: "rgba(52,211,153,0.4)",
            borderRadius: 1,
            transform: "translateX(-50%)",
          }} />
        )}
      </div>

      {/* Legend row */}
      <div style={{
        display: "flex", justifyContent: "center", gap: "var(--space-md)",
        marginTop: 8, fontSize: 9, color: "var(--color-text-muted)",
      }}>
        {bearCase != null && (
          <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{ width: 2, height: 8, background: "var(--color-error)", borderRadius: 1, display: "inline-block" }} />
            Bear
          </span>
        )}
        <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
          <span style={{
            width: 7, height: 7, transform: "rotate(45deg)",
            border: "1.5px solid var(--color-text)", borderRadius: 1, display: "inline-block",
          }} />
          Current
        </span>
        {compositeTarget != null && (
          <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{
              width: 7, height: 7, borderRadius: "50%",
              background: "var(--color-success)", display: "inline-block",
            }} />
            Target
          </span>
        )}
      </div>
    </div>
  );
}
