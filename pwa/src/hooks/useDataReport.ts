import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { DataReport } from "../types/models";

export function useDataReport(ticker: string | null, pollIntervalMs = 30_000) {
  const query = useQuery({
    queryKey: ["pipeline", "data-report", ticker],
    queryFn: () =>
      apiFetch<DataReport>(
        `/api/invest/pipeline/data-report/${encodeURIComponent(ticker!)}`,
      ),
    enabled: !!ticker,
    refetchInterval: pollIntervalMs,
    refetchIntervalInBackground: false,
  });
  return {
    report: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
}
