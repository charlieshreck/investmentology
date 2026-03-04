import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { Decision } from "../types/models";
import type { DecisionsResponse } from "../types/api";

export function useDecisions(pageSize = 20) {
  const [page, setPage] = useState(1);
  const [allDecisions, setAllDecisions] = useState<Decision[]>([]);

  const query = useQuery({
    queryKey: ["decisions", page, pageSize],
    queryFn: () => apiFetch<DecisionsResponse>(
      `/api/invest/decisions?page=${page}&pageSize=${pageSize}`,
    ),
    placeholderData: (prev) => prev, // Keep previous data while fetching next page
  });

  const fetchPage = useCallback(
    async (p: number) => {
      setPage(p);
      // When fetching page 1, reset accumulated list
      if (p === 1) setAllDecisions([]);
    },
    [],
  );

  // Accumulate decisions as pages load
  const currentDecisions = query.data?.decisions ?? [];
  const decisions = page === 1
    ? currentDecisions
    : [...allDecisions.slice(0, (page - 1) * pageSize), ...currentDecisions];

  // Track accumulated decisions for append mode
  if (query.data && decisions.length > allDecisions.length) {
    setAllDecisions(decisions);
  }

  return {
    decisions,
    total: query.data?.total ?? 0,
    page, pageSize,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    fetchPage,
  };
}
