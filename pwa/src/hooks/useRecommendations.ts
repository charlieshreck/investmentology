import { useCallback, useEffect, useState } from "react";
import type { Recommendation } from "../types/models";
import type { RecommendationsResponse } from "../types/api";

export function useRecommendations() {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [groupedByVerdict, setGroupedByVerdict] = useState<Record<string, Recommendation[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRecommendations = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/invest/recommendations");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: RecommendationsResponse = await res.json();
      setItems(data.items);
      setGroupedByVerdict(data.groupedByVerdict);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  return { items, groupedByVerdict, totalCount: items.length, loading, error, refetch: fetchRecommendations };
}
