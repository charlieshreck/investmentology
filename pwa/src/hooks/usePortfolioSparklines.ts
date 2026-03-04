import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";

interface SparklineData {
  sparklines: Record<string, Array<{ date: string; close: number }>>;
}

export function usePortfolioSparklines(positionCount: number) {
  return useQuery({
    queryKey: ["portfolio", "sparklines"],
    queryFn: () => apiFetch<SparklineData>("/portfolio/sparklines"),
    enabled: positionCount > 0,
    staleTime: 5 * 60 * 1000,
  });
}
