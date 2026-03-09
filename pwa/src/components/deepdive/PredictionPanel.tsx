import { CollapsiblePanel } from "./CollapsiblePanel";
import { Badge } from "../shared/Badge";
import { PriceRangeBar } from "../shared/PriceRangeBar";
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
