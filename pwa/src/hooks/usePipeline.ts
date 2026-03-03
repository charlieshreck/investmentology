import { useEffect, useState, useCallback } from "react";
import type {
  PipelineStatus,
  PipelineTickerSummary,
  PipelineStepDetail,
} from "../types/models";

export function usePipelineStatus() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/invest/pipeline/status");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PipelineStatus = await res.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 15_000); // Poll every 15s
    return () => clearInterval(interval);
  }, [refresh]);

  return { status, loading, error, refresh };
}

export function usePipelineTickers(cycleId?: string) {
  const [tickers, setTickers] = useState<PipelineTickerSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const url = cycleId
        ? `/api/invest/pipeline/tickers?cycle_id=${encodeURIComponent(cycleId)}`
        : "/api/invest/pipeline/tickers";
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTickers(data.tickers ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [cycleId]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 15_000);
    return () => clearInterval(interval);
  }, [refresh]);

  return { tickers, loading, error, refresh };
}

export function usePipelineTickerDetail(ticker: string | null) {
  const [steps, setSteps] = useState<PipelineStepDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) {
      setSteps([]);
      return;
    }
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        const res = await fetch(
          `/api/invest/pipeline/ticker/${encodeURIComponent(ticker!)}`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setSteps(data.steps ?? []);
          setError(null);
        }
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, 10_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [ticker]);

  return { steps, loading, error };
}
