import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { AnalysisOverviewTicker } from "../types/models";

export function useAnalysisOverview(
  scope: "portfolio" | "watchlist" | "recommendations" | "custom",
  customTickers?: string[],
) {
  const tickersParam =
    scope === "custom" && customTickers?.length
      ? `&tickers=${customTickers.join(",")}`
      : "";

  const query = useQuery({
    queryKey: ["analysis-overview", scope, customTickers],
    queryFn: () =>
      apiFetch<{ scope: string; tickers: AnalysisOverviewTicker[] }>(
        `/api/invest/pipeline/analysis-overview?scope=${scope}${tickersParam}`,
      ),
    enabled: scope !== "custom" || (customTickers?.length ?? 0) > 0,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });

  return {
    tickers: query.data?.tickers ?? [],
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
}
