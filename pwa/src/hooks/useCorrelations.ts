import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";

export interface Correlation {
  ticker1: string;
  ticker2: string;
  value: number;
}

interface CorrelationData {
  tickers: string[];
  correlations: Correlation[];
}

export function useCorrelations(positionCount: number, tickerFingerprint: string) {
  const query = useQuery({
    queryKey: ["correlations", tickerFingerprint],
    queryFn: () => apiFetch<CorrelationData>("/api/invest/portfolio/correlations"),
    enabled: positionCount >= 2,
  });

  return {
    data: query.data ?? null,
    loading: query.isLoading,
  };
}
