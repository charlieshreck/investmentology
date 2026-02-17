import type { PipelineStep } from "../../types/models";

interface ProgressStepsProps {
  steps: PipelineStep[];
}

const statusColors: Record<PipelineStep["status"], string> = {
  pending: "var(--color-surface-3)",
  active: "var(--color-accent)",
  done: "var(--color-success)",
  error: "var(--color-error)",
};

export function ProgressSteps({ steps }: ProgressStepsProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-sm)",
        overflowX: "auto",
        padding: "var(--space-sm) 0",
      }}
    >
      {steps.map((step, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-sm)",
          }}
        >
          {/* Step dot */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "var(--space-xs)",
              minWidth: 48,
            }}
          >
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: "var(--radius-full)",
                background: statusColors[step.status],
                boxShadow:
                  step.status === "active"
                    ? `0 0 8px var(--color-accent-glow)`
                    : "none",
                transition: `all var(--duration-normal) var(--ease-out)`,
              }}
            />
            <span
              style={{
                fontSize: "var(--text-xs)",
                color:
                  step.status === "active"
                    ? "var(--color-text)"
                    : "var(--color-text-muted)",
                whiteSpace: "nowrap",
              }}
            >
              {step.label}
            </span>
          </div>

          {/* Connector line */}
          {i < steps.length - 1 && (
            <div
              style={{
                width: 16,
                height: 1,
                background:
                  step.status === "done"
                    ? "var(--color-success)"
                    : "var(--color-surface-3)",
                flexShrink: 0,
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}
