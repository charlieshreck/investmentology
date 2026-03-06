import { useEffect, useState } from "react";
import { usePipelineTickerDetail } from "../../hooks/usePipeline";
import type { PipelineStepDetail } from "../../types/models";

interface PipelineActivityPillProps {
  ticker: string;
  onDismiss: () => void;
  /** Optional error from the trigger mutation */
  triggerError?: string | null;
}

function stepLabel(step: string): string {
  if (step.startsWith("agent:")) return step.slice(6);
  return step.replace(/_/g, " ");
}

function StepDot({ status }: { status: PipelineStepDetail["status"] }) {
  const colors: Record<string, string> = {
    completed: "var(--color-success)",
    running: "var(--color-accent-bright)",
    pending: "var(--color-text-muted)",
    failed: "var(--color-error)",
    expired: "var(--color-warning)",
  };
  return (
    <span
      style={{
        display: "inline-block",
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: colors[status] ?? "var(--color-text-muted)",
        flexShrink: 0,
        animation: status === "running" ? "pulse-glow 1.5s ease-in-out infinite" : "none",
      }}
    />
  );
}

export function PipelineActivityPill({
  ticker,
  onDismiss,
  triggerError,
}: PipelineActivityPillProps) {
  const { detail } = usePipelineTickerDetail(ticker, 3_000);
  const [autoDismissed, setAutoDismissed] = useState(false);

  const steps = detail?.steps ?? [];
  const completed = steps.filter((s) => s.status === "completed").length;
  const running = steps.filter((s) => s.status === "running");
  const failed = steps.filter((s) => s.status === "failed");
  const pending = steps.filter((s) => s.status === "pending");
  const total = steps.length;
  const allDone = total > 0 && pending.length === 0 && running.length === 0;

  // Auto-dismiss 4s after all steps complete
  useEffect(() => {
    if (allDone && !autoDismissed) {
      const t = setTimeout(() => {
        setAutoDismissed(true);
        onDismiss();
      }, 4000);
      return () => clearTimeout(t);
    }
  }, [allDone, autoDismissed, onDismiss]);

  // Determine current status line
  let statusText: string;
  let statusColor = "var(--color-text-secondary)";

  if (triggerError) {
    statusText = `Error: ${triggerError}`;
    statusColor = "var(--color-error)";
  } else if (total === 0) {
    statusText = "Queued — waiting for controller...";
  } else if (allDone) {
    if (failed.length > 0) {
      statusText = `Done — ${failed.length} step${failed.length > 1 ? "s" : ""} failed`;
      statusColor = "var(--color-warning)";
    } else {
      statusText = "Complete";
      statusColor = "var(--color-success)";
    }
  } else if (running.length > 0) {
    const runningNames = running.map((s) => stepLabel(s.step)).join(", ");
    statusText = `${runningNames}`;
  } else if (pending.length > 0) {
    statusText = "Waiting for next step...";
  } else {
    statusText = "Processing...";
  }

  // Progress percentage
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "var(--color-surface-0)",
        borderBottom: "1px solid var(--glass-border)",
        padding: "var(--space-sm) var(--space-lg)",
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      {/* Top row: label + dismiss */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
        {/* Spinner or check */}
        {allDone ? (
          <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke={statusColor} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ) : (
          <svg
            width={14}
            height={14}
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--color-accent-bright)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ animation: "spin 1s linear infinite" }}
          >
            <path d="M21 12a9 9 0 11-6.22-8.56" />
            <polyline points="21 3 21 12 12 12" />
          </svg>
        )}

        <span
          style={{
            flex: 1,
            fontSize: "var(--text-xs)",
            fontWeight: 600,
            color: "var(--color-text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Pipeline {total > 0 && `· ${completed}/${total}`}
        </span>

        {total > 0 && (
          <span
            style={{
              fontSize: "var(--text-xs)",
              fontFamily: "var(--font-mono)",
              color: statusColor,
            }}
          >
            {pct}%
          </span>
        )}

        <button
          onClick={onDismiss}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: 2,
            color: "var(--color-text-muted)",
            fontSize: "var(--text-xs)",
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div
          style={{
            height: 2,
            background: "var(--color-surface-2)",
            borderRadius: 1,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${pct}%`,
              background:
                failed.length > 0
                  ? "var(--color-warning)"
                  : allDone
                    ? "var(--color-success)"
                    : "var(--color-accent-bright)",
              borderRadius: 1,
              transition: "width 0.3s ease",
            }}
          />
        </div>
      )}

      {/* Status line */}
      <div
        style={{
          fontSize: 11,
          color: statusColor,
          display: "flex",
          alignItems: "center",
          gap: "var(--space-xs)",
          minHeight: 16,
        }}
      >
        {running.length > 0 && <StepDot status="running" />}
        <span style={{ fontFamily: "var(--font-mono)" }}>{statusText}</span>
      </div>

      {/* Failed steps detail */}
      {failed.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 2 }}>
          {failed.map((s) => (
            <span
              key={s.step}
              title={s.error ?? "Failed"}
              style={{
                fontSize: 10,
                fontFamily: "var(--font-mono)",
                padding: "1px 6px",
                borderRadius: "var(--radius-sm)",
                background: "rgba(248,113,113,0.1)",
                color: "var(--color-error)",
                border: "1px solid rgba(248,113,113,0.2)",
              }}
            >
              {stepLabel(s.step)}: {s.error?.slice(0, 40) ?? "failed"}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
