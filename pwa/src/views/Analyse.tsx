import { useState, useEffect, useRef } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { ProgressSteps } from "../components/shared/ProgressSteps";
import { useAnalysis } from "../contexts/AnalysisContext";
import { useConfetti } from "../hooks/useConfetti";
import { useStore } from "../stores/useStore";
import type { AnalysisProgress } from "../types/models";

export function Analyse() {
  const [ticker, setTicker] = useState("");
  const { startAnalysis, cancelAnalysis } = useAnalysis();
  const analysisProgress = useStore((s) => s.analysisProgress);
  const { fire } = useConfetti();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);

  // Keep a local snapshot of the last completed analysis so it survives
  // the status bar's auto-dismiss (which clears analysisProgress to null)
  const lastResult = useRef<AnalysisProgress | null>(null);
  const isDone = analysisProgress?.steps.every(
    (s) => s.status === "done" || s.status === "error",
  );

  // Capture completed analysis into local snapshot
  useEffect(() => {
    if (isDone && analysisProgress) {
      lastResult.current = analysisProgress;
    }
  }, [isDone, analysisProgress]);

  // Use live progress when available, otherwise show the last completed snapshot
  const displayProgress = analysisProgress ?? lastResult.current;
  const displayDone = displayProgress?.steps.every(
    (s) => s.status === "done" || s.status === "error",
  );

  useEffect(() => {
    if (isDone && analysisProgress?.result?.decisionType === "BUY") {
      fire("milestone", `analysis-${analysisProgress.result.ticker}`);
    }
  }, [isDone, analysisProgress?.result?.decisionType, analysisProgress?.result?.ticker, fire]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (t) {
      lastResult.current = null; // Clear old result when starting new analysis
      startAnalysis([t]);
    }
  };

  const isRunning = analysisProgress !== null;

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader title="Analyze" subtitle="On-demand stock analysis" />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Ticker Input */}
        <BentoCard>
          <form onSubmit={handleSubmit} style={{ display: "flex", gap: "var(--space-md)" }}>
            <input
              type="text"
              placeholder="Enter ticker (e.g., AAPL)"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              disabled={isRunning && !isDone}
              style={{
                flex: 1,
                padding: "var(--space-md) var(--space-lg)",
                background: "var(--color-surface-1)",
                border: "1px solid var(--glass-border)",
                borderRadius: "var(--radius-sm)",
                color: "var(--color-text)",
                fontSize: "var(--text-base)",
                fontFamily: "var(--font-mono)",
                outline: "none",
                letterSpacing: "0.05em",
              }}
              onFocus={(e) => { (e.target as HTMLInputElement).style.boxShadow = "var(--ring-accent)"; }}
              onBlur={(e) => { (e.target as HTMLInputElement).style.boxShadow = "none"; }}
            />
            {isRunning && !isDone ? (
              <button
                type="button"
                onClick={cancelAnalysis}
                style={{
                  padding: "var(--space-md) var(--space-xl)",
                  background: "var(--color-surface-2)",
                  border: "1px solid var(--glass-border)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--color-error)",
                  fontSize: "var(--text-sm)",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
            ) : (
              <button
                type="submit"
                disabled={!ticker.trim()}
                style={{
                  padding: "var(--space-md) var(--space-xl)",
                  background: ticker.trim() ? "var(--gradient-active)" : "var(--color-surface-2)",
                  border: "none",
                  borderRadius: "var(--radius-sm)",
                  color: ticker.trim() ? "white" : "var(--color-text-muted)",
                  fontSize: "var(--text-sm)",
                  fontWeight: 600,
                  cursor: ticker.trim() ? "pointer" : "not-allowed",
                  transition: `opacity var(--duration-fast) var(--ease-out)`,
                }}
              >
                Analyze
              </button>
            )}
          </form>
        </BentoCard>

        {/* Progress / Result */}
        {displayProgress && (
          <BentoCard title={displayDone ? `Analysis: ${displayProgress.ticker}` : `Analyzing ${displayProgress.ticker}`}>
            <ProgressSteps steps={displayProgress.steps} />

            {/* Current step detail */}
            {!displayDone && (
              <div style={{ marginTop: "var(--space-lg)", textAlign: "center" }}>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                  Running: {displayProgress.steps[displayProgress.currentStep]?.label ?? "..."}
                </div>
                <div
                  style={{
                    marginTop: "var(--space-md)",
                    height: 2,
                    background: "var(--color-surface-2)",
                    borderRadius: "var(--radius-full)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: "60%",
                      background: "var(--gradient-active)",
                      borderRadius: "var(--radius-full)",
                      animation: "shimmer 1.5s infinite",
                    }}
                  />
                </div>
              </div>
            )}

            {/* Result */}
            {displayDone && displayProgress.result && (
              <div style={{ marginTop: "var(--space-lg)", padding: "var(--space-lg)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-md)" }}>
                  <span style={{ fontWeight: 600, color: "var(--color-accent-bright)" }}>
                    {displayProgress.result.ticker}
                  </span>
                  <Badge
                    variant={
                      displayProgress.result.decisionType === "BUY" ? "success" :
                      displayProgress.result.decisionType === "SELL" ? "error" :
                      displayProgress.result.decisionType === "REJECT" ? "error" :
                      "accent"
                    }
                  >
                    {displayProgress.result.decisionType}
                  </Badge>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-sm)" }}>
                  <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>Confidence</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                    {(displayProgress.result.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                  {displayProgress.result.reasoning}
                </div>

                {/* Agent Stances */}
                {displayProgress.agentStances && displayProgress.agentStances.length > 0 && (
                  <div style={{ marginTop: "var(--space-lg)", borderTop: "1px solid var(--glass-border)", paddingTop: "var(--space-md)" }}>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-sm)" }}>
                      Agent Consensus
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
                      {displayProgress.agentStances.map((s) => (
                        <div key={s.name} style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", padding: "var(--space-xs) var(--space-sm)", background: "var(--color-surface-1)", borderRadius: "var(--radius-sm)" }}>
                          <span style={{ fontWeight: 600, fontSize: "var(--text-sm)", minWidth: 64 }}>
                            {s.name.charAt(0).toUpperCase() + s.name.slice(1)}
                          </span>
                          <div style={{ flex: 1, display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
                            <div style={{ flex: 1, height: 4, borderRadius: 2, background: "var(--color-surface-2)", overflow: "hidden" }}>
                              <div style={{
                                width: `${Math.round((s.sentiment + 1) * 50)}%`,
                                height: "100%",
                                borderRadius: 2,
                                background: s.sentiment > 0.1 ? "var(--color-success)" : s.sentiment < -0.1 ? "var(--color-error)" : "var(--color-warning)",
                              }} />
                            </div>
                            <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: s.sentiment > 0.1 ? "var(--color-success)" : s.sentiment < -0.1 ? "var(--color-error)" : "var(--color-warning)" }}>
                              {s.sentiment > 0 ? "+" : ""}{s.sentiment.toFixed(2)}
                            </span>
                          </div>
                          <Badge
                            variant={s.confidence >= 0.7 ? "success" : s.confidence >= 0.4 ? "warning" : "error"}
                          >
                            {(s.confidence * 100).toFixed(0)}%
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* View Deep Dive button */}
                <button
                  onClick={() => setOverlayTicker(displayProgress.result!.ticker)}
                  style={{
                    marginTop: "var(--space-lg)",
                    width: "100%",
                    padding: "var(--space-md)",
                    background: "var(--gradient-active)",
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    color: "#fff",
                    fontSize: "var(--text-sm)",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  View Full Analysis
                </button>
              </div>
            )}

            {/* Error state */}
            {displayDone && !displayProgress.result && displayProgress.steps.some((s) => s.status === "error") && (
              <div style={{ marginTop: "var(--space-lg)", padding: "var(--space-lg)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
                <Badge variant="error">Analysis failed</Badge>
                <p style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-sm)", marginTop: "var(--space-md)" }}>
                  One or more pipeline stages encountered an error. Check the system logs for details.
                </p>
              </div>
            )}
          </BentoCard>
        )}

        {/* Help text when idle */}
        {!displayProgress && (
          <BentoCard>
            <div style={{ textAlign: "center", padding: "var(--space-xl) 0" }}>
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, marginBottom: "var(--space-md)" }}>
                Full Pipeline Analysis
              </div>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6, maxWidth: 360, margin: "0 auto" }}>
                Enter a ticker to run the complete analysis pipeline:
                Competence Filter, Multi-Agent Analysis, Adversarial Review,
                and Timing/Sizing assessment.
              </div>
              <div style={{ display: "flex", justifyContent: "center", gap: "var(--space-sm)", marginTop: "var(--space-lg)", flexWrap: "wrap" }}>
                <Badge variant="neutral">L2 Competence</Badge>
                <Badge variant="neutral">L3 Agents</Badge>
                <Badge variant="neutral">L4 Adversarial</Badge>
                <Badge variant="neutral">L5 Timing</Badge>
              </div>
            </div>
          </BentoCard>
        )}

        <div style={{ height: "var(--nav-height)" }} />
      </div>

      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
      `}</style>
    </div>
  );
}
