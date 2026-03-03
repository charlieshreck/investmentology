import { CollapsiblePanel } from "./CollapsiblePanel";
import { Metric } from "./Metric";
import { Badge } from "../shared/Badge";
import { FormattedProse } from "../shared/FormattedProse";
import type { CompetenceData } from "../../views/StockDeepDive";

export function CompetencePanel({ competence }: { competence: CompetenceData }) {
  const preview = (
    <span style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
      <Badge variant={competence.passed ? "success" : "warning"}>
        {competence.passed ? "In Circle" : "Outside Circle"}
      </Badge>
      {competence.confidence != null && (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
          {(competence.confidence * 100).toFixed(0)}% confidence
        </span>
      )}
    </span>
  );

  return (
    <CollapsiblePanel title="Competence & Moat" preview={preview}>
      {/* Competence badges */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", marginBottom: "var(--space-md)", flexWrap: "wrap" }}>
        {competence.sector_familiarity && (
          <Badge variant={competence.sector_familiarity === "high" ? "success" : competence.sector_familiarity === "medium" ? "warning" : "error"}>
            {competence.sector_familiarity} familiarity
          </Badge>
        )}
      </div>

      {/* Competence reasoning */}
      <FormattedProse text={competence.reasoning} />

      {/* Moat section */}
      {competence.moat && (
        <div style={{ marginTop: "var(--space-md)", paddingTop: "var(--space-md)", borderTop: "1px solid var(--glass-border)" }}>
          <div style={{
            fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-sm)",
          }}>
            Moat Analysis
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)", marginBottom: "var(--space-sm)" }}>
            <Metric label="Moat Type" value={competence.moat.type || "none"} />
            <Metric label="Trajectory" value={competence.moat.trajectory || "—"} />
            <Metric label="Durability" value={`${competence.moat.durability_years}y`} mono />
          </div>
          {competence.moat.sources?.length > 0 && (
            <div style={{ display: "flex", gap: "var(--space-xs)", flexWrap: "wrap", marginBottom: "var(--space-sm)" }}>
              {competence.moat.sources.map((s: string) => <Badge key={s} variant="accent">{s.replace(/_/g, " ")}</Badge>)}
            </div>
          )}
          <FormattedProse text={competence.moat.reasoning} />
        </div>
      )}
    </CollapsiblePanel>
  );
}
