import { CollapsiblePanel } from "./CollapsiblePanel";
import { Badge } from "../shared/Badge";
import { FormattedProse } from "../shared/FormattedProse";
import type { VerdictData, CompetenceData } from "../../views/StockDeepDive";
import type { AdversarialResult } from "../../types/models";

function likelihoodBorderColor(likelihood: string): string {
  if (likelihood === "high") return "var(--color-error)";
  if (likelihood === "medium") return "var(--color-warning)";
  return "var(--color-text-muted)";
}

export function RiskPanel({ verdict, competence, adversarial }: {
  verdict: VerdictData | null;
  competence: CompetenceData | null;
  adversarial?: AdversarialResult | null;
}) {
  const riskFlags = verdict?.riskFlags ?? [];
  const concerns: { advisor: string; concern: string }[] = [];
  if (verdict?.advisoryOpinions) {
    for (const op of verdict.advisoryOpinions) {
      if (op.key_concern) concerns.push({ advisor: op.display_name, concern: op.key_concern });
    }
  }
  const narrative = verdict?.boardNarrative;
  const moat = competence?.moat;
  const killScenarios = adversarial?.kill_scenarios ?? [];
  const premortem = adversarial?.premortem;

  const totalFlags = riskFlags.length + concerns.length +
    (narrative?.risk_summary ? 1 : 0) + (narrative?.pre_mortem ? 1 : 0) +
    killScenarios.length + (premortem ? 1 : 0);

  if (totalFlags === 0) return null;

  return (
    <CollapsiblePanel
      title="Risk & Red Flags"
      variant="error"
      preview={`${totalFlags} risk item${totalFlags !== 1 ? "s" : ""} identified`}
      badge={<Badge variant={totalFlags >= 3 ? "error" : "warning"}>{totalFlags}</Badge>}
    >
      {/* Kill Scenarios (adversarial) */}
      {killScenarios.length > 0 && (
        <div style={{ marginBottom: "var(--space-lg)" }}>
          <div style={{
            fontSize: "var(--text-xs)", fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.06em", color: "var(--color-error)",
            marginBottom: "var(--space-sm)",
          }}>
            How This Could Go Wrong
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {killScenarios.map((ks, i) => (
              <div key={i} style={{
                padding: "var(--space-md)",
                background: "var(--color-surface-0)",
                borderRadius: "var(--radius-sm)",
                borderLeft: `3px solid ${likelihoodBorderColor(ks.likelihood)}`,
              }}>
                <div style={{ display: "flex", gap: "var(--space-sm)", marginBottom: "var(--space-xs)", flexWrap: "wrap" }}>
                  <Badge variant={ks.likelihood === "high" ? "error" : ks.likelihood === "medium" ? "warning" : "neutral"}>
                    {ks.likelihood} likelihood
                  </Badge>
                  <Badge variant={ks.impact === "fatal" ? "error" : ks.impact === "severe" ? "warning" : "neutral"}>
                    {ks.impact} impact
                  </Badge>
                  {ks.timeframe && (
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                      {ks.timeframe}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-primary)", lineHeight: 1.5 }}>
                  {ks.scenario}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Adversarial Pre-mortem */}
      {premortem && (
        <div style={{
          padding: "var(--space-md)",
          background: "rgba(251, 146, 60, 0.06)",
          borderRadius: "var(--radius-sm)",
          borderLeft: "3px solid var(--color-warning)",
          marginBottom: "var(--space-lg)",
        }}>
          <div style={{
            fontSize: "var(--text-xs)", fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.06em", color: "var(--color-warning)",
            marginBottom: "var(--space-sm)",
          }}>
            Pre-Mortem: If This Goes Wrong
          </div>
          <FormattedProse text={premortem.narrative} />
          {premortem.key_risks.length > 0 && (
            <div style={{ marginTop: "var(--space-sm)" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, marginBottom: 2 }}>Key Risks</div>
              {premortem.key_risks.map((risk, i) => (
                <div key={i} style={{
                  fontSize: "var(--text-xs)", color: "var(--color-text-secondary)",
                  paddingLeft: "var(--space-sm)", lineHeight: 1.6,
                }}>
                  &bull; {risk}
                </div>
              ))}
            </div>
          )}
          {premortem.probability_estimate && (
            <div style={{ marginTop: "var(--space-sm)", display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>Probability:</span>
              <Badge variant={
                premortem.probability_estimate === "likely" ? "error" :
                premortem.probability_estimate === "plausible" ? "warning" : "neutral"
              }>
                {premortem.probability_estimate}
              </Badge>
            </div>
          )}
        </div>
      )}

      {/* Risk flags from verdict */}
      {riskFlags.length > 0 && (
        <div style={{ marginBottom: "var(--space-md)" }}>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-error)", fontWeight: 600, marginBottom: "var(--space-xs)" }}>Risk Flags</div>
          {riskFlags.map((flag, i) => (
            <div key={i} style={{
              fontSize: "var(--text-sm)",
              color: "var(--color-text-secondary)",
              paddingLeft: "var(--space-md)",
              borderLeft: "2px solid var(--color-error)",
              marginBottom: "var(--space-xs)",
              lineHeight: 1.5,
            }}>
              {flag}
            </div>
          ))}
        </div>
      )}

      {/* Advisor key concerns */}
      {concerns.length > 0 && (
        <div style={{ marginBottom: "var(--space-md)" }}>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, marginBottom: "var(--space-xs)" }}>
            Advisor Concerns
          </div>
          {concerns.map((c, i) => (
            <div key={i} style={{
              display: "flex",
              gap: "var(--space-sm)",
              fontSize: "var(--text-sm)",
              color: "var(--color-text-secondary)",
              marginBottom: "var(--space-xs)",
              lineHeight: 1.5,
            }}>
              <span style={{ fontWeight: 600, color: "var(--color-text-muted)", minWidth: 60, fontSize: "var(--text-xs)" }}>
                {c.advisor}
              </span>
              <span>{c.concern}</span>
            </div>
          ))}
        </div>
      )}

      {/* CIO Risk Assessment */}
      {narrative?.risk_summary && (
        <div style={{
          padding: "var(--space-md)",
          background: "rgba(248, 113, 113, 0.06)",
          borderRadius: "var(--radius-sm)",
          borderLeft: "3px solid var(--color-error)",
          marginBottom: "var(--space-md)",
        }}>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-error)", fontWeight: 600, marginBottom: "var(--space-xs)" }}>
            RISK ASSESSMENT
          </div>
          <FormattedProse text={narrative.risk_summary} />
        </div>
      )}

      {/* CIO Pre-mortem */}
      {narrative?.pre_mortem && (
        <div style={{
          padding: "var(--space-md)",
          background: "rgba(251, 146, 60, 0.06)",
          borderRadius: "var(--radius-sm)",
          borderLeft: "3px solid var(--color-warning)",
          marginBottom: "var(--space-md)",
        }}>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-warning)", fontWeight: 600, marginBottom: "var(--space-xs)" }}>
            CIO PRE-MORTEM
          </div>
          <FormattedProse text={narrative.pre_mortem} />
        </div>
      )}

      {/* Moat durability note */}
      {moat && moat.durability_years < 10 && (
        <div style={{
          fontSize: "var(--text-sm)",
          color: "var(--color-text-secondary)",
          padding: "var(--space-sm) var(--space-md)",
          borderLeft: "2px solid var(--color-warning)",
        }}>
          Moat durability: {moat.durability_years}y ({moat.trajectory})
        </div>
      )}
    </CollapsiblePanel>
  );
}
