import { Badge } from "../shared/Badge";
import type { BuzzData, EarningsMomentum } from "../../views/StockDeepDive";

interface SignalPillsProps {
  consensusTier: string | null;
  stabilityLabel: string | null;
  stabilityScore: number | null;
  buzz: BuzzData | null;
  earningsMomentum: EarningsMomentum | null;
}

export function SignalPills({ consensusTier, stabilityLabel, stabilityScore, buzz, earningsMomentum }: SignalPillsProps) {
  const pills: { label: string; detail: string; variant: "success" | "warning" | "error" | "accent" | "neutral" }[] = [];

  if (consensusTier) {
    pills.push({
      label: consensusTier.replace(/_/g, " "),
      detail: "Consensus",
      variant: consensusTier === "HIGH_CONVICTION" ? "success" : consensusTier === "CONTRARIAN" ? "accent" : "warning",
    });
  }

  if (stabilityLabel && stabilityLabel !== "UNKNOWN") {
    pills.push({
      label: stabilityLabel,
      detail: stabilityScore != null ? `${(stabilityScore * 100).toFixed(0)}%` : "",
      variant: stabilityLabel === "STABLE" ? "success" : stabilityLabel === "UNSTABLE" ? "error" : "warning",
    });
  }

  if (buzz) {
    pills.push({
      label: `Buzz: ${buzz.buzzLabel}`,
      detail: `${buzz.articleCount} articles`,
      variant: buzz.buzzLabel === "HIGH" ? "warning" : buzz.buzzLabel === "MODERATE" ? "neutral" : "success",
    });
  }

  if (earningsMomentum) {
    pills.push({
      label: earningsMomentum.label.replace(/_/g, " "),
      detail: earningsMomentum.beatStreak > 0 ? `${earningsMomentum.beatStreak}Q streak` : "",
      variant: earningsMomentum.label.includes("UP") ? "success" : earningsMomentum.label.includes("DOWN") ? "error" : "neutral",
    });
  }

  if (!pills.length) return null;

  return (
    <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
      {pills.map((p) => (
        <Badge key={p.label} variant={p.variant}>
          {p.label}{p.detail ? ` · ${p.detail}` : ""}
        </Badge>
      ))}
    </div>
  );
}
