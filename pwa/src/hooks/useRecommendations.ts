import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { Recommendation } from "../types/models";
import type { RecommendationsResponse, PortfolioGaps, AllocationGuidance } from "../types/api";

export function useRecommendations() {
  const query = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => apiFetch<RecommendationsResponse>("/api/invest/recommendations"),
  });

  const items: Recommendation[] = query.data?.items ?? [];
  const groupedByVerdict: Record<string, Recommendation[]> = query.data?.groupedByVerdict ?? {};
  const portfolioGaps: PortfolioGaps | undefined = query.data?.portfolioGaps;
  const allocationGuidance: AllocationGuidance | undefined = query.data?.allocationGuidance;

  return {
    items, groupedByVerdict,
    totalCount: items.length,
    portfolioGaps,
    allocationGuidance,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refetch: () => query.refetch(),
  };
}
