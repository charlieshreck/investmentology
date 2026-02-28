import { createContext, useContext, type ReactNode } from "react";
import { useAnalysisStream } from "../hooks/useAnalysisStream";
import { useStore } from "../stores/useStore";

interface AnalysisContextValue {
  startAnalysis: (tickers: string[]) => Promise<void>;
  cancelAnalysis: () => void;
  isRunning: boolean;
}

const AnalysisContext = createContext<AnalysisContextValue | null>(null);

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const { startAnalysis, cancelAnalysis } = useAnalysisStream();
  const analysisProgress = useStore((s) => s.analysisProgress);

  const isRunning =
    analysisProgress !== null &&
    !analysisProgress.steps.every(
      (s) => s.status === "done" || s.status === "error",
    );

  return (
    <AnalysisContext.Provider value={{ startAnalysis, cancelAnalysis, isRunning }}>
      {children}
    </AnalysisContext.Provider>
  );
}

export function useAnalysis() {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error("useAnalysis must be used within AnalysisProvider");
  return ctx;
}
