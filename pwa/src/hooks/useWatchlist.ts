import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useStore } from "../stores/useStore";
import { apiFetch } from "../utils/apiClient";
import type { WatchlistResponse } from "../types/api";

export function useWatchlist() {
  const setWatchlist = useStore((s) => s.setWatchlist);
  const items = useStore((s) => s.items);
  const groupedByState = useStore((s) => s.groupedByState);

  const query = useQuery({
    queryKey: ["watchlist"],
    queryFn: () => apiFetch<WatchlistResponse>("/api/invest/watchlist"),
  });

  useEffect(() => {
    if (query.data) setWatchlist(query.data.items, query.data.groupedByState);
  }, [query.data, setWatchlist]);

  return {
    items, groupedByState,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refetch: () => query.refetch(),
  };
}
