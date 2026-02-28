import { useCallback, useRef } from "react";
import { useStore } from "../stores/useStore";
import type { PipelineStep } from "../types/models";

/** Real pipeline stages emitted by the backend SSE endpoint. */
const STAGE_LABELS = [
  "Fundamentals",
  "Competence",
  "Agents",
  "Debate",
  "Adversarial",
  "Verdict",
  "Gating",
  "Persisting",
  "Complete",
] as const;

function makeSteps(activeIdx: number, error?: boolean): PipelineStep[] {
  return STAGE_LABELS.map((label, i) => ({
    label,
    status:
      i < activeIdx
        ? "done"
        : i === activeIdx
          ? error
            ? "error"
            : "active"
          : "pending",
  }));
}

function stageIndex(stage: string): number {
  const idx = STAGE_LABELS.indexOf(stage as (typeof STAGE_LABELS)[number]);
  return idx >= 0 ? idx : 0;
}

export function useAnalysisStream() {
  const setAnalysisProgress = useStore((s) => s.setAnalysisProgress);
  const analysisProgress = useStore((s) => s.analysisProgress);
  const abortRef = useRef<AbortController | null>(null);

  const startAnalysis = useCallback(
    async (tickers: string[]) => {
      if (tickers.length === 0) return;
      const primaryTicker = tickers[0];

      // Abort any existing stream
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Show initial progress
      setAnalysisProgress({
        ticker: primaryTicker,
        steps: makeSteps(0),
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
                const idx = stageIndex(event.stage);
                setAnalysisProgress((prev) =>
                  prev
                    ? {
                        ...prev,
                        ticker: event.ticker ?? prev.ticker,
                        steps: makeSteps(idx),
                        currentStep: idx,
                        tickerIndex: event.tickerIndex,
                        tickerTotal: event.tickerTotal,
                      }
                    : null,
                );
              } else if (event.type === "result") {
                const result = event.results?.[0];
                const verdict = result?.verdict;

                // Data quality error — bad fundamentals detected, analysis aborted
                if (result?.data_quality_error) {
                  setAnalysisProgress((prev) =>
                    prev
                      ? {
                          ...prev,
                          steps: makeSteps(0, true),
                          currentStep: 0,
                          errorMessage: result.data_quality_error,
                        }
                      : null,
                  );
                } else {
                  setAnalysisProgress((prev) =>
                    prev
                      ? {
                          ...prev,
                          steps: makeSteps(STAGE_LABELS.length),
                          currentStep: STAGE_LABELS.length - 1,
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
                        }
                      : null,
                  );
                }
              } else if (event.type === "error") {
                setAnalysisProgress((prev) =>
                  prev
                    ? {
                        ...prev,
                        steps: makeSteps(prev.currentStep, true),
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
                steps: makeSteps(prev.currentStep, true),
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
    setAnalysisProgress(null);
  }, [setAnalysisProgress]);

  return { analysisProgress, startAnalysis, cancelAnalysis };
}
