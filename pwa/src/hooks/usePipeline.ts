import { useEffect, useState, useCallback, useRef } from "react";
import type {
  PipelineStatus,
  PipelineTickerSummary,
  PipelineTickerDetail,
  PipelineFunnel,
  PipelineHealth,
} from "../types/models";

/**
 * Stable-state polling hook factory.
 *
 * Only shows skeleton on the very first load (when state is null).
 * Subsequent polls silently update state without flashing loading indicators.
 * Skips setState entirely if the fetched data is identical (prevents re-renders).
 * Pauses polling when the document tab is hidden.
 */
function usePollingHook<T>(
  fetchFn: () => Promise<T>,
  intervalMs: number,
  deps: unknown[] = [],
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const lastJson = useRef<string>("");

  const refresh = useCallback(async () => {
    try {
      const result = await fetchFn();
      const json = JSON.stringify(result);
      // Only update state if data actually changed
      if (json !== lastJson.current) {
        lastJson.current = json;
        setData(result);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refresh();

    // Only poll when the tab is visible
    let interval: ReturnType<typeof setInterval> | null = null;

    function startPolling() {
      if (!interval) {
        interval = setInterval(refresh, intervalMs);
      }
    }
    function stopPolling() {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    }
    function handleVisibility() {
      if (document.visibilityState === "visible") {
        refresh(); // Catch up immediately
        startPolling();
      } else {
        stopPolling();
      }
    }

    startPolling();
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [refresh, intervalMs]);

  return { data, loading, error, refresh };
}

export function usePipelineStatus() {
  const { data: status, loading, error, refresh } = usePollingHook<PipelineStatus>(
    async () => {
      const res = await fetch("/api/invest/pipeline/status");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    15_000,
  );
  return { status, loading, error, refresh };
}

export function usePipelineTickers(cycleId?: string) {
  const { data, loading, error, refresh } = usePollingHook<PipelineTickerSummary[]>(
    async () => {
      const url = cycleId
        ? `/api/invest/pipeline/tickers?cycle_id=${encodeURIComponent(cycleId)}`
        : "/api/invest/pipeline/tickers";
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      return json.tickers ?? [];
    },
    15_000,
    [cycleId],
  );
  return { tickers: data ?? [], loading, error, refresh };
}

export function usePipelineTickerDetail(ticker: string | null) {
  const [detail, setDetail] = useState<PipelineTickerDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastJson = useRef<string>("");

  useEffect(() => {
    if (!ticker) {
      setDetail(null);
      lastJson.current = "";
      return;
    }
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(
          `/api/invest/pipeline/ticker/${encodeURIComponent(ticker!)}`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: PipelineTickerDetail = await res.json();
        if (!cancelled) {
          const json = JSON.stringify(data);
          if (json !== lastJson.current) {
            lastJson.current = json;
            setDetail(data);
          }
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

    // Only poll when visible
    let interval: ReturnType<typeof setInterval> | null = null;

    function startPolling() {
      if (!interval) interval = setInterval(load, 10_000);
    }
    function stopPolling() {
      if (interval) { clearInterval(interval); interval = null; }
    }
    function handleVisibility() {
      if (document.visibilityState === "visible") {
        load();
        startPolling();
      } else {
        stopPolling();
      }
    }

    startPolling();
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      cancelled = true;
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [ticker]);

  return { detail, loading, error };
}

export function usePipelineFunnel() {
  const { data: funnel, loading, error, refresh } = usePollingHook<PipelineFunnel>(
    async () => {
      const res = await fetch("/api/invest/pipeline/funnel");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    15_000,
  );
  return { funnel, loading, error, refresh };
}

export function usePipelineHealth() {
  const { data: health, loading, error, refresh } = usePollingHook<PipelineHealth>(
    async () => {
      const res = await fetch("/api/invest/pipeline/health");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    30_000,
  );
  return { health, loading, error, refresh };
}
