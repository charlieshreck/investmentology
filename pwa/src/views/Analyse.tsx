import { useState, useEffect, useRef } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { ProgressSteps } from "../components/shared/ProgressSteps";
import { StreamText } from "../components/shared/StreamText";
import { useAnalysis } from "../contexts/AnalysisContext";
import { useConfetti } from "../hooks/useConfetti";
import { useStore } from "../stores/useStore";
import type { AnalysisProgress, AdvisoryOpinion, BoardNarrative } from "../types/models";

// ─── Advisory Board Section ────────────────────────────────────────────────

function voteColor(vote: string): string {
  switch (vote) {
    case "APPROVE":     return "var(--color-success)";
    case "VETO":        return "var(--color-error)";
    case "ADJUST_UP":   return "var(--color-accent-bright)";
    case "ADJUST_DOWN": return "var(--color-warning)";
    default:            return "var(--color-text-muted)";
  }
}

function voteLabel(vote: string): string {
  switch (vote) {
    case "APPROVE":     return "Approve";
    case "VETO":        return "Veto";
    case "ADJUST_UP":   return "Adjust Up";
    case "ADJUST_DOWN": return "Adjust Down";
    default:            return vote;
  }
}

function AdvisoryBoardSection({
  boardNarrative,
  advisoryOpinions,
  boardAdjustedVerdict,
}: {
  boardNarrative?: BoardNarrative;
  advisoryOpinions: AdvisoryOpinion[];
  boardAdjustedVerdict?: string;
}) {
  const [expanded, setExpanded] = useState(false);

  const approve    = advisoryOpinions.filter((o) => o.vote === "APPROVE").length;
  const veto       = advisoryOpinions.filter((o) => o.vote === "VETO").length;
  const adjustUp   = advisoryOpinions.filter((o) => o.vote === "ADJUST_UP").length;
  const adjustDown = advisoryOpinions.filter((o) => o.vote === "ADJUST_DOWN").length;
  const total      = advisoryOpinions.length;

  return (
    <div style={{ marginTop: "var(--space-lg)", borderTop: "1px solid var(--glass-border)", paddingTop: "var(--space-md)" }}>
      {/* Section header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-md)" }}>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Advisory Board
        </div>
        {boardAdjustedVerdict && (
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
            <Badge variant="accent">Board Adjusted</Badge>
            <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "var(--text-sm)" }}>
              {boardAdjustedVerdict}
            </span>
          </div>
        )}
      </div>

      {/* CIO Synthesis Card */}
      {boardNarrative && (
        <div style={{
          padding: "var(--space-md)",
          background: "var(--color-surface-1)",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--glass-border)",
          marginBottom: "var(--space-md)",
        }}>
          <p style={{ fontSize: "var(--text-base)", fontWeight: 700, color: "var(--color-text)", lineHeight: 1.4, margin: "0 0 var(--space-xs) 0" }}>
            {boardNarrative.headline}
          </p>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.5, margin: "0 0 var(--space-md) 0" }}>
            {boardNarrative.risk_summary}
          </p>

          {/* Board vote summary bar */}
          {total > 0 && (
            <div>
              <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", gap: 1 }}>
                {approve > 0 && (
                  <div style={{ flex: approve, background: "var(--color-success)", borderRadius: "3px 0 0 3px" }} />
                )}
                {adjustUp > 0 && (
                  <div style={{ flex: adjustUp, background: "var(--color-accent-bright)" }} />
                )}
                {adjustDown > 0 && (
                  <div style={{ flex: adjustDown, background: "var(--color-warning)" }} />
                )}
                {veto > 0 && (
                  <div style={{ flex: veto, background: "var(--color-error)", borderRadius: "0 3px 3px 0" }} />
                )}
              </div>
              <div style={{ display: "flex", gap: "var(--space-md)", marginTop: "var(--space-xs)" }}>
                {approve > 0 && (
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-success)", fontWeight: 600 }}>
                    {approve} Approve
                  </span>
                )}
                {adjustUp > 0 && (
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-accent-bright)", fontWeight: 600 }}>
                    {adjustUp} Adjust Up
                  </span>
                )}
                {adjustDown > 0 && (
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-warning)", fontWeight: 600 }}>
                    {adjustDown} Adjust Down
                  </span>
                )}
                {veto > 0 && (
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-error)", fontWeight: 600 }}>
                    {veto} Veto
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Advisor Grid — 2 columns */}
      {advisoryOpinions.length > 0 && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--space-sm)",
          marginBottom: "var(--space-md)",
        }}>
          {advisoryOpinions.map((op) => {
            const color = voteColor(op.vote);
            return (
              <div key={op.advisor_name} style={{
                padding: "var(--space-sm)",
                background: "var(--color-surface-1)",
                borderRadius: "var(--radius-sm)",
                borderTop: `3px solid ${color}`,
              }}>
                {/* Name + vote pill */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-xs)" }}>
                  <span style={{ fontWeight: 700, fontSize: "var(--text-sm)", color: "var(--color-text)" }}>
                    {op.display_name}
                  </span>
                  <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    color,
                    background: `${color}22`,
                    padding: "2px 6px",
                    borderRadius: 4,
                    letterSpacing: "0.03em",
                  }}>
                    {voteLabel(op.vote)}
                  </span>
                </div>

                {/* Confidence bar */}
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-xs)", marginBottom: "var(--space-xs)" }}>
                  <div style={{ flex: 1, height: 3, background: "var(--color-surface-2)", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ width: `${(op.confidence * 100).toFixed(0)}%`, height: "100%", background: color, borderRadius: 2 }} />
                  </div>
                  <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)", flexShrink: 0 }}>
                    {(op.confidence * 100).toFixed(0)}%
                  </span>
                </div>

                {/* One-line assessment */}
                {op.assessment && (
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.4, margin: "0 0 var(--space-xs) 0", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                    {op.assessment}
                  </p>
                )}

                {/* Key concern / endorsement */}
                {op.key_concern && (
                  <p style={{ fontSize: 10, color: "var(--color-error)", margin: 0, lineHeight: 1.3 }}>
                    Risk: {op.key_concern}
                  </p>
                )}
                {!op.key_concern && op.key_endorsement && (
                  <p style={{ fontSize: 10, color: "var(--color-success)", margin: 0, lineHeight: 1.3 }}>
                    Edge: {op.key_endorsement}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Full Narrative — expandable */}
      {boardNarrative && (boardNarrative.narrative || boardNarrative.pre_mortem || boardNarrative.conflict_resolution) && (
        <div>
          <button
            onClick={() => setExpanded((v) => !v)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-xs)",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--color-text-muted)",
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              padding: 0,
              marginBottom: expanded ? "var(--space-sm)" : 0,
            }}
          >
            <span style={{ transform: expanded ? "rotate(90deg)" : "none", display: "inline-block", transition: "transform 0.15s" }}>▶</span>
            {expanded ? "Hide" : "Full"} Board Analysis
          </button>

          {expanded && (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {boardNarrative.narrative && (
                <div style={{ padding: "var(--space-sm)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-xs)" }}>
                    Narrative
                  </div>
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.6, margin: 0 }}>
                    {boardNarrative.narrative}
                  </p>
                </div>
              )}
              {boardNarrative.pre_mortem && (
                <div style={{ padding: "var(--space-sm)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-xs)" }}>
                    Pre-Mortem
                  </div>
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.6, margin: 0 }}>
                    {boardNarrative.pre_mortem}
                  </p>
                </div>
              )}
              {boardNarrative.conflict_resolution && (
                <div style={{ padding: "var(--space-sm)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-xs)" }}>
                    Conflict Resolution
                  </div>
                  <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.6, margin: 0 }}>
                    {boardNarrative.conflict_resolution}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main View ────────────────────────────────────────────────────────────────

export function Analyse() {
  const [ticker, setTicker] = useState("");
  const { startAnalysis, cancelAnalysis } = useAnalysis();
  const analysisProgress = useStore((s) => s.analysisProgress);
  const recentAnalyses = useStore((s) => s.recentAnalyses);
  const pushRecentAnalysis = useStore((s) => s.pushRecentAnalysis);
  const { fire } = useConfetti();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);

  // Keep a local snapshot of the last completed analysis so it survives
  // the status bar's auto-dismiss (which clears analysisProgress to null)
  const lastResult = useRef<AnalysisProgress | null>(null);
  const isDone = analysisProgress?.steps.every(
    (s) => s.status === "done" || s.status === "error",
  );

  // Capture completed analysis into local snapshot + recent history
  useEffect(() => {
    if (isDone && analysisProgress) {
      lastResult.current = analysisProgress;
      if (analysisProgress.result) {
        pushRecentAnalysis({
          ticker: analysisProgress.result.ticker,
          decisionType: analysisProgress.result.decisionType,
          confidence: analysisProgress.result.confidence,
          reasoning: analysisProgress.result.reasoning,
          agentStances: analysisProgress.agentStances,
          riskFlags: analysisProgress.riskFlags,
          consensusScore: analysisProgress.consensusScore,
          completedAt: new Date().toISOString(),
        });
      }
    }
  }, [isDone, analysisProgress, pushRecentAnalysis]);

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
                    {displayProgress.result.confidence != null
                      ? `${(displayProgress.result.confidence * 100).toFixed(0)}%`
                      : "—"}
                  </span>
                </div>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
                  <StreamText text={displayProgress.result.reasoning} speed={6} />
                </div>

                {/* Agent Stances */}
                {displayProgress.agentStances && displayProgress.agentStances.length > 0 && (
                  <div style={{ marginTop: "var(--space-lg)", borderTop: "1px solid var(--glass-border)", paddingTop: "var(--space-md)" }}>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-sm)" }}>
                      Agent Consensus
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                      {displayProgress.agentStances.map((s) => {
                        const sentColor = s.sentiment > 0.1 ? "var(--color-success)" : s.sentiment < -0.1 ? "var(--color-error)" : "var(--color-warning)";
                        return (
                          <div key={s.name} style={{ padding: "var(--space-sm) var(--space-md)", background: "var(--color-surface-1)", borderRadius: "var(--radius-sm)" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
                              <span style={{ fontWeight: 600, fontSize: "var(--text-sm)", minWidth: 64 }}>
                                {s.name.charAt(0).toUpperCase() + s.name.slice(1)}
                              </span>
                              <div style={{ flex: 1, display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
                                <div style={{ flex: 1, height: 4, borderRadius: 2, background: "var(--color-surface-2)", overflow: "hidden" }}>
                                  <div style={{
                                    width: `${Math.round((s.sentiment + 1) * 50)}%`,
                                    height: "100%",
                                    borderRadius: 2,
                                    background: sentColor,
                                  }} />
                                </div>
                                <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: sentColor }}>
                                  {s.sentiment > 0 ? "+" : ""}{s.sentiment.toFixed(2)}
                                </span>
                              </div>
                              <Badge
                                variant={s.confidence >= 0.7 ? "success" : s.confidence >= 0.4 ? "warning" : "error"}
                              >
                                {(s.confidence * 100).toFixed(0)}%
                              </Badge>
                            </div>
                            {s.summary && s.summary !== "Failed to parse LLM response" && (
                              <p style={{
                                fontSize: "var(--text-xs)", color: "var(--color-text-secondary)",
                                lineHeight: 1.5, margin: "var(--space-xs) 0 0 0",
                              }}>
                                {s.summary.length > 200 ? s.summary.slice(0, 200) + "..." : s.summary}
                              </p>
                            )}
                            {s.key_signals && s.key_signals.length > 0 && (
                              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: "var(--space-xs)" }}>
                                {s.key_signals.map((sig, i) => (
                                  <span key={i} style={{
                                    fontSize: 9, padding: "1px 6px", borderRadius: 4,
                                    background: "var(--color-surface-2)", color: "var(--color-text-muted)",
                                    fontWeight: 600,
                                  }}>
                                    {sig}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Advisory Board — CIO Synthesis + Advisor Grid */}
                {(displayProgress.boardNarrative || (displayProgress.advisoryOpinions && displayProgress.advisoryOpinions.length > 0)) && (
                  <AdvisoryBoardSection
                    boardNarrative={displayProgress.boardNarrative}
                    advisoryOpinions={displayProgress.advisoryOpinions ?? []}
                    boardAdjustedVerdict={displayProgress.boardAdjustedVerdict}
                  />
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
                <Badge variant="neutral">L5 Verdict</Badge>
                <Badge variant="neutral">L5.5 Advisory Board</Badge>
                <Badge variant="neutral">L6 CIO</Badge>
              </div>
            </div>
          </BentoCard>
        )}

        {/* Recent Analyses */}
        {recentAnalyses.length > 0 && (
          <BentoCard title="Recent Analyses">
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {recentAnalyses.map((a) => {
                const verdictColor =
                  a.decisionType === "BUY" || a.decisionType === "STRONG_BUY" || a.decisionType === "ACCUMULATE"
                    ? "success"
                    : a.decisionType === "SELL" || a.decisionType === "REJECT"
                      ? "error"
                      : a.decisionType === "HOLD"
                        ? "warning"
                        : "neutral";
                const timeAgo = (() => {
                  const ms = Date.now() - new Date(a.completedAt).getTime();
                  const mins = Math.floor(ms / 60000);
                  if (mins < 1) return "just now";
                  if (mins < 60) return `${mins}m ago`;
                  const hrs = Math.floor(mins / 60);
                  if (hrs < 24) return `${hrs}h ago`;
                  return `${Math.floor(hrs / 24)}d ago`;
                })();
                return (
                  <div
                    key={`${a.ticker}-${a.completedAt}`}
                    onClick={() => setOverlayTicker(a.ticker)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-md)",
                      padding: "var(--space-sm) var(--space-md)",
                      borderRadius: "var(--radius-sm)",
                      cursor: "pointer",
                      transition: "background var(--duration-fast) var(--ease-out)",
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-1)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                  >
                    <span style={{ fontWeight: 700, fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", minWidth: 48 }}>
                      {a.ticker}
                    </span>
                    <Badge variant={verdictColor}>{a.decisionType}</Badge>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
                      {(a.confidence * 100).toFixed(0)}%
                    </span>
                    <div style={{ flex: 1, fontSize: "var(--text-xs)", color: "var(--color-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {a.reasoning}
                    </div>
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", flexShrink: 0 }}>
                      {timeAgo}
                    </span>
                  </div>
                );
              })}
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
