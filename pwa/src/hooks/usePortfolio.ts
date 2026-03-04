import { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useStore } from "../stores/useStore";
import { apiFetch } from "../utils/apiClient";
import type { PortfolioResponse, ClosedPositionsResponse } from "../types/api";

export function usePortfolio() {
  const queryClient = useQueryClient();
  const setPortfolio = useStore((s) => s.setPortfolio);
  const positions = useStore((s) => s.positions);
  const totalValue = useStore((s) => s.totalValue);
  const dayPnl = useStore((s) => s.dayPnl);
  const dayPnlPct = useStore((s) => s.dayPnlPct);
  const cash = useStore((s) => s.cash);
  const alerts = useStore((s) => s.alerts);

  const portfolioQuery = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => apiFetch<PortfolioResponse>("/api/invest/portfolio"),
  });

  // Sync to Zustand store
  useEffect(() => {
    if (portfolioQuery.data) setPortfolio(portfolioQuery.data);
  }, [portfolioQuery.data, setPortfolio]);

  const closedQuery = useQuery({
    queryKey: ["portfolio", "closed"],
    queryFn: () => apiFetch<ClosedPositionsResponse>("/api/invest/portfolio/closed"),
  });

  const addPositionMutation = useMutation({
    mutationFn: (data: {
      ticker: string;
      entry_price: number;
      shares: number;
      position_type?: string;
      weight?: number;
      stop_loss?: number | null;
      fair_value_estimate?: number | null;
      thesis?: string;
    }) =>
      apiFetch("/api/invest/portfolio/positions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });

  const closePositionMutation = useMutation({
    mutationFn: ({ positionId, exitPrice }: { positionId: number; exitPrice: number }) =>
      apiFetch(`/api/invest/portfolio/positions/${positionId}/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exit_price: exitPrice }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });

  return {
    positions, totalValue, dayPnl, dayPnlPct, cash, alerts,
    closedPositions: closedQuery.data?.closedPositions ?? [],
    totalRealizedPnl: closedQuery.data?.totalRealizedPnl ?? 0,
    loading: portfolioQuery.isLoading,
    error: portfolioQuery.error?.message ?? null,
    refetch: () => portfolioQuery.refetch(),
    addPosition: addPositionMutation.mutateAsync,
    closePosition: (positionId: number, exitPrice: number) =>
      closePositionMutation.mutateAsync({ positionId, exitPrice }),
  };
}
