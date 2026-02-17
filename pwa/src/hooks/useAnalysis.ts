import { useCallback } from "react";
import { useStore } from "../stores/useStore";
import type { PipelineStep } from "../types/models";

const STEPS: PipelineStep[] = [
  { label: "Competence", status: "pending" },
  { label: "Agents", status: "pending" },
  { label: "Adversarial", status: "pending" },
  { label: "Verdict", status: "pending" },
];

function makeSteps(activeIdx: number, error?: boolean): PipelineStep[] {
  return STEPS.map((s, i) => ({
    ...s,
    status: i < activeIdx ? "done" : i === activeIdx ? (error ? "error" : "active") : "pending",
  }));
}

export function useAnalysis() {
  const setAnalysisProgress = useStore((s) => s.setAnalysisProgress);
  const analysisProgress = useStore((s) => s.analysisProgress);

  const startAnalysis = useCallback(
    async (ticker: string) => {
      // Show initial progress
      setAnalysisProgress({
        ticker,
        steps: makeSteps(0),
        currentStep: 0,
      });

      try {
        // Animate through steps while waiting for response
        const stepTimer = setInterval(() => {
          setAnalysisProgress((prev) => {
            if (!prev || prev.currentStep >= 3) return prev;
            const next = prev.currentStep + 1;
            return { ...prev, steps: makeSteps(next), currentStep: next };
          });
        }, 8000);

        const res = await fetch("/api/invest/analyse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tickers: [ticker] }),
        });

        clearInterval(stepTimer);

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const result = data.results?.[0];
        const verdict = result?.verdict;

        setAnalysisProgress({
          ticker,
          steps: makeSteps(4), // all done
          currentStep: 3,
          result: verdict
            ? {
                id: data.analysis_id,
                ticker,
                decisionType: verdict.recommendation,
                confidence: verdict.confidence,
                reasoning: verdict.reasoning,
                createdAt: new Date().toISOString(),
                layer: "L4",
              }
            : result?.competence && !result.passed_competence
              ? {
                  id: data.analysis_id,
                  ticker,
                  decisionType: "COMPETENCE_FAIL",
                  confidence: result.competence.confidence,
                  reasoning: result.competence.reasoning,
                  createdAt: new Date().toISOString(),
                  layer: "L2",
                }
              : undefined,
        });
      } catch (err) {
        setAnalysisProgress((prev) =>
          prev
            ? {
                ...prev,
                steps: makeSteps(prev.currentStep, true),
              }
            : null,
        );
      }
    },
    [setAnalysisProgress],
  );

  const cancelAnalysis = useCallback(() => {
    setAnalysisProgress(null);
  }, [setAnalysisProgress]);

  return { analysisProgress, startAnalysis, cancelAnalysis };
}
