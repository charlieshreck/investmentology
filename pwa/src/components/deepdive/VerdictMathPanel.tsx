import { BentoCard } from "../shared/BentoCard";
import { Badge } from "../shared/Badge";
import type { VerdictData } from "../../views/StockDeepDive";

/**
 * Verdict Math Panel — shows the weighted sentiment, confidence breakdown,
 * position type, margin to boundary, conviction gap, and per-agent contributions.
 */
export function VerdictMathPanel({ verdict }: { verdict: VerdictData }) {
  const hasContribs = verdict.agentContributions && verdict.agentContributions.length > 0;
  const hasAnyData =
    verdict.verdictMargin != null ||
    verdict.convictionGap != null ||
    verdict.positionType ||
    verdict.regimeLabel ||
    hasContribs;

  if (!hasAnyData) return null;

  // Find max vote power for bar chart scaling
  const maxVotePower = hasContribs
    ? Math.max(...verdict.agentContributions!.map((a) => Math.abs(a.votePower)), 0.01)
    : 1;

  return (
    <BentoCard title="Verdict Math">
      {/* Summary row */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-lg)",
          flexWrap: "wrap",
          marginBottom: "var(--space-md)",
        }}
      >
        {verdict.consensusScore != null && (
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              Sentiment
            </div>
            <div
              style={{
                fontSize: "var(--text-lg)",
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
                color:
                  verdict.consensusScore > 0.1
                    ? "var(--color-success)"
                    : verdict.consensusScore < -0.1
                      ? "var(--color-error)"
                      : "var(--color-text-secondary)",
              }}
            >
              {verdict.consensusScore > 0 ? "+" : ""}
              {verdict.consensusScore.toFixed(3)}
            </div>
          </div>
        )}

        {verdict.confidence != null && (
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              Confidence
            </div>
            <div
              style={{
                fontSize: "var(--text-lg)",
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
              }}
            >
              {Math.round(verdict.confidence * 100)}%
            </div>
          </div>
        )}

        {verdict.verdictMargin != null && (
          <div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              Margin to Boundary
            </div>
            <div
              style={{
                fontSize: "var(--text-lg)",
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
                color:
                  Math.abs(verdict.verdictMargin) < 0.05
                    ? "var(--color-warning)"
                    : "var(--color-text-primary)",
              }}
            >
              {verdict.verdictMargin > 0 ? "+" : ""}
              {verdict.verdictMargin.toFixed(3)}
            </div>
          </div>
        )}
      </div>

      {/* Tags row */}
      <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap", marginBottom: "var(--space-md)" }}>
        {verdict.positionType && (
          <Badge variant="neutral">{verdict.positionType.toUpperCase()}</Badge>
        )}
        {verdict.regimeLabel && (
          <Badge variant="neutral">{verdict.regimeLabel}</Badge>
        )}
        {verdict.convictionGap && (
          <Badge variant="warning">Conviction Gap</Badge>
        )}
        {verdict.watchlistReason && (
          <Badge variant="accent">{verdict.watchlistReason}</Badge>
        )}
      </div>

      {/* Headcount summary */}
      {verdict.headcountSummary && (
        <div
          style={{
            fontSize: "var(--text-sm)",
            color: "var(--color-text-secondary)",
            marginBottom: "var(--space-md)",
          }}
        >
          {verdict.headcountSummary}
        </div>
      )}

      {/* Agent contribution bars */}
      {hasContribs && (
        <div>
          <div
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
              marginBottom: "var(--space-sm)",
              fontWeight: 600,
            }}
          >
            Agent Contributions (weight x confidence)
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {verdict.agentContributions!
              .sort((a, b) => Math.abs(b.votePower) - Math.abs(a.votePower))
              .map((agent) => {
                const barPct = Math.abs(agent.votePower) / maxVotePower;
                const isBullish = agent.sentiment > 0.1;
                const isBearish = agent.sentiment < -0.1;
                const barColor = isBullish
                  ? "var(--color-success)"
                  : isBearish
                    ? "var(--color-error)"
                    : "var(--color-text-muted)";

                return (
                  <div key={agent.name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        width: 90,
                        fontSize: "var(--text-xs)",
                        fontFamily: "var(--font-mono)",
                        textTransform: "capitalize",
                        flexShrink: 0,
                      }}
                    >
                      {agent.name}
                    </span>
                    <div
                      style={{
                        flex: 1,
                        height: 12,
                        backgroundColor: "var(--color-surface-secondary)",
                        borderRadius: 4,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${barPct * 100}%`,
                          height: "100%",
                          backgroundColor: barColor,
                          borderRadius: 4,
                          transition: "width 0.3s ease",
                        }}
                      />
                    </div>
                    <span
                      style={{
                        width: 48,
                        fontSize: 10,
                        fontFamily: "var(--font-mono)",
                        textAlign: "right",
                        color: "var(--color-text-muted)",
                        flexShrink: 0,
                      }}
                    >
                      {(agent.weight * 100).toFixed(0)}%
                    </span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Watchlist graduation trigger */}
      {verdict.watchlistGraduationTrigger && (
        <div
          style={{
            marginTop: "var(--space-md)",
            padding: "var(--space-sm) var(--space-md)",
            backgroundColor: "var(--color-surface-secondary)",
            borderRadius: "var(--radius-sm)",
            fontSize: "var(--text-xs)",
            color: "var(--color-text-secondary)",
          }}
        >
          <strong>Graduation trigger:</strong> {verdict.watchlistGraduationTrigger}
        </div>
      )}
    </BentoCard>
  );
}
