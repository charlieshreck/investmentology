import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { Recommendation } from "../types/models";
import type { RecommendationsResponse } from "../types/api";

export function useRecommendations() {
  const query = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => apiFetch<RecommendationsResponse>("/api/invest/recommendations"),
  });

  const items: Recommendation[] = query.data?.items ?? [];
  const groupedByVerdict: Record<string, Recommendation[]> = query.data?.groupedByVerdict ?? {};

  return {
    items, groupedByVerdict,
    totalCount: items.length,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refetch: () => query.refetch(),
  };
}
