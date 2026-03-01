import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useStore } from "../../stores/useStore";

const VERDICT_COLORS: Record<string, string> = {
  BUY: "var(--color-success)",
  STRONG_BUY: "var(--color-success)",
  ACCUMULATE: "var(--color-success)",
  HOLD: "var(--color-warning)",
  SELL: "var(--color-error)",
  REJECT: "var(--color-error)",
  COMPETENCE_FAIL: "var(--color-text-muted)",
};

const BAR_STYLE: React.CSSProperties = {
  background: "var(--color-surface-1)",
  borderBottom: "1px solid var(--glass-border)",
  padding: "0 var(--space-md)",
  height: 40,
  display: "flex",
  alignItems: "center",
  gap: "var(--space-md)",
  fontSize: "var(--text-xs)",
  zIndex: 90,
  flexShrink: 0,
};

const DISMISS_STYLE: React.CSSProperties = {
  background: "none",
  border: "none",
  color: "var(--color-text-muted)",
  cursor: "pointer",
  padding: 2,
  fontSize: 14,
  lineHeight: 1,
};

export function AnalysisStatusBar() {
  const progress = useStore((s) => s.analysisProgress);
  const setProgress = useStore((s) => s.setAnalysisProgress);
  const screener = useStore((s) => s.screenerProgress);
  const setScreener = useStore((s) => s.setScreenerProgress);
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  const isDone = progress?.steps.every(
    (s) => s.status === "done" || s.status === "error",
  );
  const hasError = progress?.steps.some((s) => s.status === "error");
  const verdict = progress?.result?.decisionType;

  // Auto-dismiss 8s after analysis completion
  useEffect(() => {
    if (isDone && !hasError) {
      dismissTimer.current = setTimeout(() => {
        setProgress(null);
      }, 8000);
    }
    return () => {
      if (dismissTimer.current) clearTimeout(dismissTimer.current);
    };
  }, [isDone, hasError, setProgress]);

  // Screener mode: show linear progress bar when no analysis is active
  if (!progress && screener) {
    const isComplete = screener.stage === "complete";
    const isError = screener.stage === "error";
    return (
      <div
        style={{ ...BAR_STYLE, cursor: "pointer" }}
        onClick={() => navigate("/analyze")}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter") navigate("/analyze"); }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            color: "var(--color-accent-bright)",
            letterSpacing: "0.05em",
          }}
        >
          SCREEN
        </span>
        <span
          style={{
            color: isError
              ? "var(--color-error)"
              : isComplete
                ? "var(--color-success)"
                : "var(--color-text-secondary)",
            fontWeight: isComplete || isError ? 600 : 400,
          }}
        >
          {screener.stage}
          {screener.detail ? ` \u2014 ${screener.detail}` : ""}
        </span>
        <div style={{ flex: 1 }} />
        <div
          style={{
            width: 80,
            height: 3,
            borderRadius: 2,
            background: "var(--color-surface-3)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${screener.pct}%`,
              height: "100%",
              background: isError ? "var(--color-error)" : "var(--gradient-active)",
              borderRadius: 2,
              transition: "width 0.5s ease",
            }}
          />
        </div>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "var(--text-xs)",
            color: "var(--color-text-muted)",
            minWidth: 28,
            textAlign: "right",
          }}
        >
          {screener.pct}%
        </span>
        <button onClick={(e) => { e.stopPropagation(); setScreener(null); }} style={DISMISS_STYLE} aria-label="Dismiss">
          ×
        </button>
      </div>
    );
  }

  if (!progress) return null;

  const activeStep = progress.steps.find((s) => s.status === "active");
  const doneCount = progress.steps.filter((s) => s.status === "done").length;
  const totalSteps = progress.steps.length;
  const pct = isDone ? 100 : (doneCount / totalSteps) * 100;

  const tickerLabel =
    progress.tickerTotal && progress.tickerTotal > 1
      ? `${progress.ticker} (${progress.tickerIndex ?? 1}/${progress.tickerTotal})`
      : progress.ticker;

  return (
    <div
      style={{ ...BAR_STYLE, cursor: "pointer" }}
      onClick={() => navigate("/analyze")}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter") navigate("/analyze"); }}
    >
      {/* Left: ticker + stage */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-sm)",
          minWidth: 0,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            color: "var(--color-accent-bright)",
            letterSpacing: "0.05em",
          }}
        >
          {tickerLabel}
        </span>
        {isDone ? (
          verdict ? (
            <span
              style={{
                fontWeight: 600,
                color: VERDICT_COLORS[verdict] ?? "var(--color-text)",
              }}
            >
              {verdict}
              {progress.result?.confidence != null &&
                ` ${(progress.result.confidence * 100).toFixed(0)}%`}
            </span>
          ) : hasError ? (
            <span style={{ color: "var(--color-error)", fontWeight: 600 }}>
              Failed
            </span>
          ) : (
            <span style={{ color: "var(--color-text-muted)" }}>Done</span>
          )
        ) : (
          <span style={{ color: "var(--color-text-secondary)" }}>
            {activeStep?.label ?? "Starting..."}
          </span>
        )}
      </div>

      {/* Center: progress dots */}
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 4,
        }}
      >
        {progress.steps.map((step, i) => (
          <div
            key={i}
            title={step.label}
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background:
                step.status === "done"
                  ? "var(--color-success)"
                  : step.status === "active"
                    ? "var(--color-accent)"
                    : step.status === "error"
                      ? "var(--color-error)"
                      : "var(--color-surface-3)",
              boxShadow:
                step.status === "active"
                  ? "0 0 6px var(--color-accent-glow)"
                  : "none",
              transition: "all 0.3s ease",
            }}
          />
        ))}
      </div>

      {/* Right: progress bar + dismiss */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-sm)",
          flexShrink: 0,
        }}
      >
        {!isDone && (
          <div
            style={{
              width: 48,
              height: 3,
              borderRadius: 2,
              background: "var(--color-surface-3)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${pct}%`,
                height: "100%",
                background: "var(--gradient-active)",
                borderRadius: 2,
                transition: "width 0.5s ease",
              }}
            />
          </div>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); setProgress(null); }}
          style={DISMISS_STYLE}
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
    </div>
  );
}
