import { motion } from "framer-motion";
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
            <motion.div
              initial={{ scale: 0 }}
              animate={{
                scale: step.status === "active" ? [1, 1.3, 1] : 1,
                backgroundColor: statusColors[step.status],
              }}
              transition={
                step.status === "active"
                  ? { scale: { repeat: Infinity, duration: 1.5, ease: "easeInOut" }, backgroundColor: { duration: 0.3 } }
                  : { type: "spring", stiffness: 400, damping: 25 }
              }
              style={{
                width: 10,
                height: 10,
                borderRadius: "var(--radius-full)",
                boxShadow:
                  step.status === "active"
                    ? `0 0 8px var(--color-accent-glow)`
                    : "none",
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
                flexShrink: 0,
                background: "var(--color-surface-3)",
                position: "relative",
                overflow: "hidden",
              }}
            >
              <motion.div
                initial={{ scaleX: 0 }}
                animate={{ scaleX: step.status === "done" ? 1 : 0 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  position: "absolute",
                  inset: 0,
                  background: "var(--color-success)",
                  transformOrigin: "left",
                }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
