import { useCallback, useRef } from "react";
import { useStore } from "../stores/useStore";
import type { PipelineStep } from "../types/models";

/**
 * Base pipeline stages (non-agent). Agent stages are inserted dynamically
 * between "Competence" and "Verdict" as agent_start/agent_complete events arrive.
 */
const PRE_AGENT_STAGES = ["Fundamentals", "Competence"] as const;
const POST_AGENT_STAGES = ["Debate", "Adversarial", "Verdict", "Advisory Board", "CIO Synthesis", "Gating", "Persisting", "Complete"] as const;

/** Check if a stage name is a known non-agent pipeline stage */
function isKnownStage(stage: string): boolean {
  return (
    (PRE_AGENT_STAGES as readonly string[]).includes(stage) ||
    (POST_AGENT_STAGES as readonly string[]).includes(stage)
  );
}

function buildSteps(
  agents: string[],
  activeStage: string,
  error?: boolean,
): PipelineStep[] {
  const allStages = [
    ...PRE_AGENT_STAGES,
    ...agents,
    ...POST_AGENT_STAGES,
  ];

  const activeIdx = allStages.indexOf(activeStage);
  const resolvedIdx = activeIdx >= 0 ? activeIdx : 0;

  return allStages.map((label, i) => ({
    label,
    status:
      i < resolvedIdx
        ? "done"
        : i === resolvedIdx
          ? error
            ? "error"
            : "active"
          : "pending",
  }));
}

function buildDoneSteps(agents: string[]): PipelineStep[] {
  const allStages = [
    ...PRE_AGENT_STAGES,
    ...agents,
    ...POST_AGENT_STAGES,
  ];
  return allStages.map((label) => ({ label, status: "done" as const }));
}

export function useAnalysisStream() {
  const setAnalysisProgress = useStore((s) => s.setAnalysisProgress);
  const analysisProgress = useStore((s) => s.analysisProgress);
  const abortRef = useRef<AbortController | null>(null);
  /** Track discovered agent names (order-preserving) */
  const agentsRef = useRef<string[]>([]);

  const startAnalysis = useCallback(
    async (tickers: string[]) => {
      if (tickers.length === 0) return;
      const primaryTicker = tickers[0];

      // Abort any existing stream
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Reset agent tracking
      agentsRef.current = [];

      // Show initial progress
      setAnalysisProgress({
        ticker: primaryTicker,
        steps: buildSteps([], PRE_AGENT_STAGES[0]),
        currentStep: 0,
        tickerTotal: tickers.length > 1 ? tickers.length : undefined,
        tickerIndex: tickers.length > 1 ? 1 : undefined,
      });

      try {
        const res = await fetch("/api/invest/analyse/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ tickers }),
          signal: controller.signal,
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (!res.body) throw new Error("No response body");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          // Keep the last incomplete line in the buffer
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const json = line.slice(6).trim();
            if (!json) continue;

            try {
              const event = JSON.parse(json);

              if (event.type === "progress") {
                const stage: string = event.stage ?? "";

                // If stage is not a known pipeline stage, treat it as an agent name
                if (stage && !isKnownStage(stage) && !agentsRef.current.includes(stage)) {
                  agentsRef.current = [...agentsRef.current, stage];
                }

                const agents = agentsRef.current;
                const steps = buildSteps(agents, stage);
                const idx = steps.findIndex((s) => s.status === "active");

                setAnalysisProgress((prev) =>
                  prev
                    ? {
                        ...prev,
                        ticker: event.ticker ?? prev.ticker,
                        steps,
                        currentStep: idx >= 0 ? idx : 0,
                        tickerIndex: event.tickerIndex,
                        tickerTotal: event.tickerTotal,
                      }
                    : null,
                );
              } else if (event.type === "agent_start") {
                // Dynamic agent discovery from agent_start events
                const agentName: string = event.agent ?? "";
                if (agentName && !agentsRef.current.includes(agentName)) {
                  agentsRef.current = [...agentsRef.current, agentName];
                }

                const agents = agentsRef.current;
                const steps = buildSteps(agents, agentName);
                const idx = steps.findIndex((s) => s.status === "active");

                setAnalysisProgress((prev) =>
                  prev
                    ? {
                        ...prev,
                        steps,
                        currentStep: idx >= 0 ? idx : prev.currentStep,
                      }
                    : null,
                );
              } else if (event.type === "agent_complete") {
                // Mark agent as done by advancing past it
                const agentName: string = event.agent ?? "";
                const agents = agentsRef.current;
                const allStages = [...PRE_AGENT_STAGES, ...agents, ...POST_AGENT_STAGES];
                const agentIdx = allStages.indexOf(agentName);
                // Build steps with this agent done (active = next stage)
                if (agentIdx >= 0 && agentIdx + 1 < allStages.length) {
                  const nextStage = allStages[agentIdx + 1];
                  const steps = buildSteps(agents, nextStage);
                  setAnalysisProgress((prev) =>
                    prev
                      ? {
                          ...prev,
                          steps,
                          currentStep: agentIdx + 1,
                        }
                      : null,
                  );
                }
              } else if (event.type === "result") {
                const result = event.results?.[0];
                const verdict = result?.verdict;

                // Data quality error — bad fundamentals detected, analysis aborted
                if (result?.data_quality_error) {
                  setAnalysisProgress((prev) =>
                    prev
                      ? {
                          ...prev,
                          steps: buildSteps(agentsRef.current, PRE_AGENT_STAGES[0], true),
                          currentStep: 0,
                          errorMessage: result.data_quality_error,
                        }
                      : null,
                  );
                } else {
                  const agents = agentsRef.current;
                  setAnalysisProgress((prev) =>
                    prev
                      ? {
                          ...prev,
                          steps: buildDoneSteps(agents),
                          currentStep: PRE_AGENT_STAGES.length + agents.length + POST_AGENT_STAGES.length - 1,
                          result: verdict
                            ? {
                                id: event.analysis_id,
                                ticker: result.ticker,
                                decisionType: verdict.recommendation,
                                confidence: verdict.confidence,
                                reasoning: verdict.reasoning,
                                createdAt: new Date().toISOString(),
                                layer: "L4",
                              }
                            : result?.competence && !result.passed_competence
                              ? {
                                  id: event.analysis_id,
                                  ticker: result.ticker,
                                  decisionType: "COMPETENCE_FAIL",
                                  confidence: result.competence.confidence,
                                  reasoning: result.competence.reasoning,
                                  createdAt: new Date().toISOString(),
                                  layer: "L2",
                                }
                              : undefined,
                          agentStances: verdict?.agent_stances ?? undefined,
                          riskFlags: verdict?.risk_flags ?? undefined,
                          consensusScore: verdict?.consensus_score ?? null,
                          advisoryOpinions: verdict?.advisory_opinions ?? undefined,
                          boardNarrative: verdict?.board_narrative ?? undefined,
                          boardAdjustedVerdict: verdict?.board_adjusted_verdict ?? undefined,
                        }
                      : null,
                  );
                }
              } else if (event.type === "error") {
                setAnalysisProgress((prev) =>
                  prev
                    ? {
                        ...prev,
                        steps: buildSteps(
                          agentsRef.current,
                          prev.steps[prev.currentStep]?.label ?? PRE_AGENT_STAGES[0],
                          true,
                        ),
                        errorMessage: event.message,
                      }
                    : null,
                );
              }
            } catch {
              // Skip malformed SSE lines
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setAnalysisProgress((prev) =>
          prev
            ? {
                ...prev,
                steps: buildSteps(
                  agentsRef.current,
                  prev.steps[prev.currentStep]?.label ?? PRE_AGENT_STAGES[0],
                  true,
                ),
                errorMessage: (err as Error).message,
              }
            : null,
        );
      }
    },
    [setAnalysisProgress],
  );

  const cancelAnalysis = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    agentsRef.current = [];
    setAnalysisProgress(null);
  }, [setAnalysisProgress]);

  return { analysisProgress, startAnalysis, cancelAnalysis };
}
