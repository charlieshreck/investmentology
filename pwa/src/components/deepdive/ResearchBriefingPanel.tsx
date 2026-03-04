import { CollapsiblePanel } from "./CollapsiblePanel";
import { Badge } from "../shared/Badge";
import { FormattedProse } from "../shared/FormattedProse";
import type { ResearchBriefing } from "../../views/StockDeepDive";

export function ResearchBriefingPanel({ briefing }: { briefing: ResearchBriefing }) {
  if (!briefing.content) return null;

  return (
    <CollapsiblePanel
      title="Deep Research"
      variant="accent"
      preview={`${briefing.sourceCount} sources analyzed`}
      badge={<Badge variant="accent">AI Research</Badge>}
    >
      <FormattedProse text={briefing.content} />
      {briefing.createdAt && (
        <div style={{
          marginTop: "var(--space-md)",
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
          textAlign: "right",
        }}>
          Researched {new Date(briefing.createdAt).toLocaleDateString()}
        </div>
      )}
    </CollapsiblePanel>
  );
}
