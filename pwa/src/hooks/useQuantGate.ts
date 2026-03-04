import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useStore } from "../stores/useStore";
import { apiFetch } from "../utils/apiClient";
import type { QuantGateResponse } from "../types/api";

export function useQuantGate() {
  const setQuantGate = useStore((s) => s.setQuantGate);
  const latestRun = useStore((s) => s.latestRun);
  const topResults = useStore((s) => s.topResults);

  const query = useQuery({
    queryKey: ["quant-gate", "latest"],
    queryFn: () => apiFetch<QuantGateResponse>("/api/invest/quant-gate/latest"),
  });

  useEffect(() => {
    if (query.data?.latestRun) setQuantGate(query.data.latestRun);
  }, [query.data, setQuantGate]);

  return {
    latestRun, topResults,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refetch: () => query.refetch(),
  };
}
