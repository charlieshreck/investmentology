import { CollapsiblePanel } from "./CollapsiblePanel";
import { Badge } from "../shared/Badge";
import type { PredictionCard } from "../../types/models";

// ─── Conviction tier → visual mapping ─────────────────────────────────────

const TIER_CONFIG: Record<string, { label: string; variant: "success" | "accent" | "warning" | "error" | "neutral"; color: string }> = {
  ALL_SIGNALS_ALIGNED: { label: "All Signals Aligned", variant: "success", color: "var(--color-success)" },
  HIGH_CONVICTION:     { label: "High Conviction",     variant: "accent",  color: "var(--color-accent-bright)" },
  MODERATE:            { label: "Moderate",             variant: "warning", color: "var(--color-warning)" },
  LOW_CONVICTION:      { label: "Low Conviction",      variant: "neutral", color: "var(--color-text-muted)" },
  MIXED_SIGNALS:       { label: "Mixed Signals",       variant: "error",   color: "var(--color-error)" },
};

function tierConfig(tier: string) {
  return TIER_CONFIG[tier] ?? TIER_CONFIG.MODERATE;
}

// ─── Formatting helpers ───────────────────────────────────────────────────

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function fmtPct(v: number | null | undefined, showSign = true): string {
  if (v == null) return "—";
  const sign = showSign && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

function pctColor(v: number | null | undefined): string {
  if (v == null) return "var(--color-text-muted)";
  return v >= 0 ? "var(--color-success)" : "var(--color-error)";
}

// ─── Visual Price Range Bar ───────────────────────────────────────────────

function PriceRangeBar({ card }: { card: PredictionCard }) {
  const { bearCase, currentPrice, compositeTarget, targetRangeHigh } = card;

  // Need at least current + one other point
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

// ─── Signal Pill ──────────────────────────────────────────────────────────

function SignalPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{
      padding: "6px var(--space-sm)",
      background: "var(--color-surface-0)",
      borderRadius: "var(--radius-sm)",
      border: "1px solid var(--glass-border)",
      display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
    }}>
      <span style={{
        fontSize: 9, fontWeight: 600, textTransform: "uppercase",
        letterSpacing: "0.04em", color: "var(--color-text-muted)",
      }}>
        {label}
      </span>
      <span style={{
        fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", fontWeight: 700,
        color: color ?? "var(--color-text)",
      }}>
        {value}
      </span>
    </div>
  );
}

// ─── Main Panel ───────────────────────────────────────────────────────────

export function PredictionPanel({ card }: { card: PredictionCard }) {
  const tier = tierConfig(card.convictionTier);

  // Build preview text
  const previewParts: string[] = [];
  if (card.upsidePct != null && card.compositeTarget != null) {
    previewParts.push(`${fmtPct(card.upsidePct)} to ${fmtPrice(card.compositeTarget)}`);
  }
  if (card.riskRewardRatio != null) {
    previewParts.push(`${card.riskRewardRatio}:1 R/R`);
  }
  if (!previewParts.length) {
    previewParts.push(`${Math.round(card.confidence * 100)}% confidence`);
  }

  return (
    <CollapsiblePanel
      title="Prediction Card"
      variant="accent"
      defaultOpen
      preview={previewParts.join(" · ")}
      badge={<Badge variant={tier.variant} glow>{tier.label}</Badge>}
    >
      {/* ── Hero Stats ─────────────────────────────────────────────── */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-sm)",
        marginBottom: "var(--space-md)",
      }}>
        {/* Target */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-muted)", marginBottom: 2 }}>
            Target
          </div>
          <div style={{
            fontSize: "var(--text-2xl)", fontWeight: 800, fontFamily: "var(--font-mono)",
            color: "var(--color-success)",
          }}>
            {fmtPrice(card.compositeTarget)}
          </div>
        </div>

        {/* Current */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-muted)", marginBottom: 2 }}>
            Current
          </div>
          <div style={{
            fontSize: "var(--text-2xl)", fontWeight: 800, fontFamily: "var(--font-mono)",
            color: "var(--color-text)",
          }}>
            {fmtPrice(card.currentPrice)}
          </div>
        </div>

        {/* Upside */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-muted)", marginBottom: 2 }}>
            Upside
          </div>
          <div style={{
            fontSize: "var(--text-2xl)", fontWeight: 800, fontFamily: "var(--font-mono)",
            color: pctColor(card.upsidePct),
          }}>
            {fmtPct(card.upsidePct)}
          </div>
        </div>
      </div>

      {/* ── Second row: Bear / Downside / R:R ──────────────────────── */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-sm)",
        marginBottom: "var(--space-lg)",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-muted)", marginBottom: 2 }}>
            Bear Case
          </div>
          <div style={{ fontSize: "var(--text-base)", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-error)" }}>
            {fmtPrice(card.bearCase)}
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-muted)", marginBottom: 2 }}>
            Downside
          </div>
          <div style={{ fontSize: "var(--text-base)", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-error)" }}>
            {card.downsidePct != null ? `−${Math.abs(card.downsidePct).toFixed(1)}%` : "—"}
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-text-muted)", marginBottom: 2 }}>
            Risk / Reward
          </div>
          <div style={{
            fontSize: "var(--text-base)", fontWeight: 700, fontFamily: "var(--font-mono)",
            color: (card.riskRewardRatio ?? 0) >= 2
              ? "var(--color-success)"
              : (card.riskRewardRatio ?? 0) >= 1
                ? "var(--color-warning)"
                : "var(--color-error)",
          }}>
            {card.riskRewardRatio != null ? `${card.riskRewardRatio}:1` : "—"}
          </div>
        </div>
      </div>

      {/* ── Price Range Bar ────────────────────────────────────────── */}
      <div style={{
        padding: "var(--space-md)",
        background: "var(--color-surface-0)",
        borderRadius: "var(--radius-sm)",
        border: "1px solid var(--glass-border)",
        marginBottom: "var(--space-md)",
      }}>
        <PriceRangeBar card={card} />
      </div>

      {/* ── Signal Grid ────────────────────────────────────────────── */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-xs)",
        marginBottom: "var(--space-md)",
      }}>
        <SignalPill
          label="Confidence"
          value={`${Math.round(card.confidence * 100)}%`}
          color={card.confidence >= 0.7 ? "var(--color-success)" : card.confidence >= 0.5 ? "var(--color-warning)" : "var(--color-error)"}
        />
        <SignalPill
          label="Consensus"
          value={`${Math.round(card.agentConsensusPct)}%`}
          color={card.agentConsensusPct >= 75 ? "var(--color-success)" : card.agentConsensusPct >= 50 ? "var(--color-warning)" : "var(--color-error)"}
        />
        <SignalPill
          label="Quant Rank"
          value={card.quantGateRank != null ? `#${card.quantGateRank}` : "—"}
          color={card.quantGateRank != null && card.quantGateRank <= 20 ? "var(--color-success)" : undefined}
        />
        <SignalPill
          label="Piotroski"
          value={card.piotroskiScore != null ? `${card.piotroskiScore}/9` : "—"}
          color={
            card.piotroskiScore != null
              ? card.piotroskiScore >= 7 ? "var(--color-success)" : card.piotroskiScore >= 5 ? "var(--color-warning)" : "var(--color-error)"
              : undefined
          }
        />
        <SignalPill
          label="Altman"
          value={card.altmanZone ?? "—"}
          color={
            card.altmanZone === "safe" ? "var(--color-success)"
              : card.altmanZone === "grey" ? "var(--color-warning)"
                : card.altmanZone === "distress" ? "var(--color-error)"
                  : undefined
          }
        />
        <SignalPill
          label="R / R"
          value={card.riskRewardRatio != null ? `${card.riskRewardRatio}:1` : "—"}
          color={
            (card.riskRewardRatio ?? 0) >= 2 ? "var(--color-success)"
              : (card.riskRewardRatio ?? 0) >= 1 ? "var(--color-warning)"
                : "var(--color-error)"
          }
        />
      </div>

      {/* ── Agent Targets ──────────────────────────────────────────── */}
      {card.agentTargets.length > 0 && (
        <div style={{ marginBottom: "var(--space-md)" }}>
          <div style={{
            fontSize: 9, fontWeight: 600, textTransform: "uppercase",
            letterSpacing: "0.05em", color: "var(--color-text-muted)",
            marginBottom: "var(--space-xs)",
          }}>
            Agent Price Targets
          </div>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: "var(--space-xs)",
          }}>
            {[...card.agentTargets]
              .sort((a, b) => b.weight - a.weight)
              .map((t) => (
                <div
                  key={t.agent}
                  style={{
                    display: "flex", alignItems: "center", gap: "var(--space-sm)",
                    padding: "4px var(--space-sm)",
                    background: "var(--color-surface-0)",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--glass-border)",
                  }}
                >
                  <span style={{
                    fontSize: 11, fontWeight: 600, color: "var(--color-text-secondary)",
                    flex: 1, textTransform: "capitalize",
                  }}>
                    {t.agent}
                  </span>
                  <span style={{
                    fontSize: 11, fontFamily: "var(--font-mono)", fontWeight: 700,
                    color: t.targetPrice > card.currentPrice ? "var(--color-success)" : "var(--color-error)",
                  }}>
                    {fmtPrice(t.targetPrice)}
                  </span>
                  <span style={{
                    fontSize: 9, fontFamily: "var(--font-mono)",
                    color: "var(--color-text-muted)",
                  }}>
                    {Math.round(t.weight * 100)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* ── Footer: Timing & Benchmark ─────────────────────────────── */}
      <div style={{
        display: "flex", flexWrap: "wrap", gap: "var(--space-md)",
        padding: "var(--space-sm) 0",
        borderTop: "1px solid var(--glass-border)",
        fontSize: 11, color: "var(--color-text-muted)",
      }}>
        <span>
          <span style={{ fontWeight: 600 }}>Hold: </span>
          {card.holdingPeriod}
        </span>
        {card.earningsWarning && (
          <span style={{
            color: card.earningsWarning.toLowerCase().includes("defer") || card.earningsWarning.toLowerCase().includes("block")
              ? "var(--color-error)"
              : card.earningsWarning.toLowerCase().includes("caution")
                ? "var(--color-warning)"
                : "var(--color-text-muted)",
          }}>
            {card.earningsWarning}
          </span>
        )}
        {card.settlementBenchmarkSpy != null && (
          <span>
            <span style={{ fontWeight: 600 }}>SPY: </span>
            <span style={{ fontFamily: "var(--font-mono)" }}>{fmtPrice(card.settlementBenchmarkSpy)}</span>
          </span>
        )}
      </div>
    </CollapsiblePanel>
  );
}
