import { useCallback, useEffect, useState } from "react";
import { useStore } from "../stores/useStore";
import type { WatchlistResponse } from "../types/api";

export function useWatchlist() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const setWatchlist = useStore((s) => s.setWatchlist);
  const items = useStore((s) => s.items);
  const groupedByState = useStore((s) => s.groupedByState);

  const fetchWatchlist = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/invest/watchlist");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: WatchlistResponse = await res.json();
      setWatchlist(data.items, data.groupedByState);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [setWatchlist]);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  return { items, groupedByState, loading, error, refetch: fetchWatchlist };
}
