import { BentoCard } from "../shared/BentoCard";
import { Badge } from "../shared/Badge";
import { RingChart } from "../shared/RingChart";
import { verdictColor, verdictLabel } from "../../utils/verdictHelpers";
import { voteColor } from "../../utils/deepdiveHelpers";
import type { VerdictData } from "../../views/StockDeepDive";

export function HeroVerdictStrip({ verdict }: { verdict: VerdictData }) {
  const color = verdictColor[verdict.recommendation] ?? "var(--color-text-muted)";
  const label = verdictLabel[verdict.recommendation] ?? verdict.recommendation;

  // Vote tally from advisory opinions
  const tally = { approve: 0, veto: 0, adjust: 0 };
  if (verdict.advisoryOpinions) {
    for (const op of verdict.advisoryOpinions) {
      if (op.vote === "APPROVE") tally.approve++;
      else if (op.vote === "VETO") tally.veto++;
      else tally.adjust++;
    }
  }
  const hasVotes = verdict.advisoryOpinions && verdict.advisoryOpinions.length > 0;

  const confidencePct = verdict.confidence != null ? Math.round(verdict.confidence * 100) : null;
  const confidenceColor =
    (confidencePct ?? 0) >= 70 ? "var(--color-success)" :
    (confidencePct ?? 0) >= 40 ? "var(--color-warning)" :
    "var(--color-error)";

  return (
    <BentoCard variant="hero" glow>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: "var(--space-md)",
      }}>
        {/* Left: Verdict + overrides */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", flexWrap: "wrap" }}>
            <span style={{
              fontSize: "var(--text-3xl)",
              fontWeight: 800,
              color,
              fontFamily: "var(--font-mono)",
              letterSpacing: "0.02em",
              lineHeight: 1,
            }}>
              {label}
            </span>
            {verdict.auditorOverride && <Badge variant="error">Auditor Override</Badge>}
            {verdict.mungerOverride && <Badge variant="error">Munger Veto</Badge>}
          </div>

          {/* Board headline */}
          {verdict.boardNarrative?.headline && (
            <div style={{
              marginTop: "var(--space-sm)",
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              fontStyle: "italic",
              lineHeight: 1.4,
            }}>
              {verdict.boardNarrative.headline}
            </div>
          )}

          {/* Vote tally pills + consensus score */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-sm)",
            marginTop: "var(--space-md)",
            flexWrap: "wrap",
          }}>
            {hasVotes && (
              <>
                {tally.approve > 0 && (
                  <span style={{
                    fontSize: "var(--text-xs)",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                    color: voteColor("APPROVE"),
                  }}>
                    {tally.approve} Approve
                  </span>
                )}
                {tally.adjust > 0 && (
                  <span style={{
                    fontSize: "var(--text-xs)",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                    color: voteColor("ADJUST_UP"),
                  }}>
                    {tally.adjust} Adjust
                  </span>
                )}
                {tally.veto > 0 && (
                  <span style={{
                    fontSize: "var(--text-xs)",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                    color: voteColor("VETO"),
                  }}>
                    {tally.veto} Veto
                  </span>
                )}
              </>
            )}
            {verdict.consensusScore != null && (
              <span style={{
                fontSize: "var(--text-xs)",
                color: "var(--color-text-muted)",
                fontFamily: "var(--font-mono)",
              }}>
                cs: {verdict.consensusScore > 0 ? "+" : ""}{verdict.consensusScore.toFixed(3)}
              </span>
            )}
          </div>
        </div>

        {/* Right: Confidence ring */}
        {confidencePct != null && (
          <div style={{ flexShrink: 0, position: "relative" }}>
            <RingChart
              value={confidencePct}
              size={64}
              strokeWidth={5}
              color={confidenceColor}
            />
            <div style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}>
              <span style={{
                fontSize: 16,
                fontWeight: 800,
                fontFamily: "var(--font-mono)",
                color: confidenceColor,
              }}>
                {confidencePct}%
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Timestamp */}
      {verdict.createdAt && (
        <div style={{
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
          textAlign: "right",
          marginTop: "var(--space-sm)",
        }}>
          {new Date(verdict.createdAt).toLocaleString()}
        </div>
      )}
    </BentoCard>
  );
}
