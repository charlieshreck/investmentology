import { useState, useEffect } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { ProgressSteps } from "../components/shared/ProgressSteps";
import { useAnalysis } from "../hooks/useAnalysis";
import { useConfetti } from "../hooks/useConfetti";

export function Analyse() {
  const [ticker, setTicker] = useState("");
  const { analysisProgress, startAnalysis, cancelAnalysis } = useAnalysis();
  const { fire } = useConfetti();

  const isDone = analysisProgress?.steps.every(
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
      startAnalysis(t);
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

        {/* Progress */}
        {analysisProgress && (
          <BentoCard title={`Analyzing ${analysisProgress.ticker}`}>
            <ProgressSteps steps={analysisProgress.steps} />

            {/* Current step detail */}
            {!isDone && (
              <div style={{ marginTop: "var(--space-lg)", textAlign: "center" }}>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                  Running: {analysisProgress.steps[analysisProgress.currentStep]?.label ?? "..."}
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
            {isDone && analysisProgress.result && (
              <div style={{ marginTop: "var(--space-lg)", padding: "var(--space-lg)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-md)" }}>
                  <span style={{ fontWeight: 600, color: "var(--color-accent-bright)" }}>
                    {analysisProgress.result.ticker}
                  </span>
                  <Badge
                    variant={
                      analysisProgress.result.decisionType === "BUY" ? "success" :
                      analysisProgress.result.decisionType === "SELL" ? "error" :
                      analysisProgress.result.decisionType === "REJECT" ? "error" :
                      "accent"
                    }
                  >
                    {analysisProgress.result.decisionType}
                  </Badge>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-sm)" }}>
                  <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>Confidence</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                    {(analysisProgress.result.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                  {analysisProgress.result.reasoning}
                </div>
              </div>
            )}

            {/* Error state */}
            {isDone && !analysisProgress.result && analysisProgress.steps.some((s) => s.status === "error") && (
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
        {!analysisProgress && (
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
