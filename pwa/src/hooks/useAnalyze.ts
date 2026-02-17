import { useState, useCallback } from "react";

interface AnalyzeState {
  analyzing: Set<string>;
  triggerAnalysis: (ticker: string) => Promise<void>;
}

export function useAnalyze(onComplete?: (ticker: string) => void, refetchData?: () => void): AnalyzeState {
  const [analyzing, setAnalyzing] = useState<Set<string>>(new Set());

  const triggerAnalysis = useCallback(async (ticker: string) => {
    setAnalyzing((prev) => new Set(prev).add(ticker));
    try {
      const res = await fetch("/api/invest/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers: [ticker] }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onComplete?.(ticker);
      refetchData?.();
    } catch (err) {
      console.error("Analysis failed for", ticker, err);
    } finally {
      setAnalyzing((prev) => {
        const next = new Set(prev);
        next.delete(ticker);
        return next;
      });
    }
  }, [onComplete, refetchData]);

  return { analyzing, triggerAnalysis };
}
