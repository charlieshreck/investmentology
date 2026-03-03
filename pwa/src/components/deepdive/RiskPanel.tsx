import { CollapsiblePanel } from "./CollapsiblePanel";
import { Badge } from "../shared/Badge";
import { FormattedProse } from "../shared/FormattedProse";
import type { VerdictData, CompetenceData } from "../../views/StockDeepDive";

export function RiskPanel({ verdict, competence }: {
  verdict: VerdictData | null;
  competence: CompetenceData | null;
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

  const totalFlags = riskFlags.length + concerns.length +
    (narrative?.risk_summary ? 1 : 0) + (narrative?.pre_mortem ? 1 : 0);

  if (totalFlags === 0) return null;

  return (
    <CollapsiblePanel
      title="Risk & Red Flags"
      variant="error"
      preview={`${totalFlags} risk item${totalFlags !== 1 ? "s" : ""} identified`}
      badge={<Badge variant={totalFlags >= 3 ? "error" : "warning"}>{totalFlags}</Badge>}
    >
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

      {/* Pre-mortem */}
      {narrative?.pre_mortem && (
        <div style={{
          padding: "var(--space-md)",
          background: "rgba(251, 146, 60, 0.06)",
          borderRadius: "var(--radius-sm)",
          borderLeft: "3px solid var(--color-warning)",
          marginBottom: "var(--space-md)",
        }}>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-warning)", fontWeight: 600, marginBottom: "var(--space-xs)" }}>
            PRE-MORTEM
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
