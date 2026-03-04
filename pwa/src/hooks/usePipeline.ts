import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type {
  PipelineStatus,
  PipelineTickerSummary,
  PipelineTickerDetail,
  PipelineFunnel,
  PipelineHealth,
} from "../types/models";

export function usePipelineStatus() {
  const query = useQuery({
    queryKey: ["pipeline", "status"],
    queryFn: () => apiFetch<PipelineStatus>("/api/invest/pipeline/status"),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  });
  return {
    status: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
}

export function usePipelineTickers(cycleId?: string) {
  const query = useQuery({
    queryKey: ["pipeline", "tickers", cycleId],
    queryFn: async () => {
      const url = cycleId
        ? `/api/invest/pipeline/tickers?cycle_id=${encodeURIComponent(cycleId)}`
        : "/api/invest/pipeline/tickers";
      const data = await apiFetch<{ tickers: PipelineTickerSummary[] }>(url);
      return data.tickers ?? [];
    },
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  });
  return {
    tickers: query.data ?? [],
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
}

export function usePipelineTickerDetail(ticker: string | null) {
  const query = useQuery({
    queryKey: ["pipeline", "ticker", ticker],
    queryFn: () => apiFetch<PipelineTickerDetail>(
      `/api/invest/pipeline/ticker/${encodeURIComponent(ticker!)}`,
    ),
    enabled: !!ticker,
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
  });
  return {
    detail: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
  };
}

export function usePipelineFunnel() {
  const query = useQuery({
    queryKey: ["pipeline", "funnel"],
    queryFn: () => apiFetch<PipelineFunnel>("/api/invest/pipeline/funnel"),
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  });
  return {
    funnel: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
}

export function usePipelineHealth() {
  const query = useQuery({
    queryKey: ["pipeline", "health"],
    queryFn: () => apiFetch<PipelineHealth>("/api/invest/pipeline/health"),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
  return {
    health: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
}
