import { useCallback, useEffect, useState } from "react";
import { useStore } from "../stores/useStore";
import type { QuantGateResponse } from "../types/api";

export function useQuantGate() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const setQuantGate = useStore((s) => s.setQuantGate);
  const latestRun = useStore((s) => s.latestRun);
  const topResults = useStore((s) => s.topResults);

  const fetchQuantGate = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/invest/quant-gate/latest");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: QuantGateResponse = await res.json();
      if (data.latestRun) setQuantGate(data.latestRun);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [setQuantGate]);

  useEffect(() => {
    fetchQuantGate();
  }, [fetchQuantGate]);

  return { latestRun, topResults, loading, error, refetch: fetchQuantGate };
}
