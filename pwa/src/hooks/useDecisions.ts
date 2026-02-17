import { useCallback, useState } from "react";
import type { Decision } from "../types/models";
import type { DecisionsResponse } from "../types/api";

export function useDecisions(pageSize = 20) {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(
    async (p: number) => {
      try {
        setLoading(true);
        const res = await fetch(
          `/api/invest/decisions?page=${p}&pageSize=${pageSize}`,
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: DecisionsResponse = await res.json();
        setDecisions((prev) => p === 1 ? data.decisions : [...prev, ...data.decisions]);
        setTotal(data.total);
        setPage(p);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [pageSize],
  );

  return { decisions, total, page, pageSize, loading, error, fetchPage };
}
