import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";

export interface BacktestSummary {
  startDate: string;
  endDate: string;
  initialCapital: number;
  finalValue: number;
  totalReturn: number;
  annualizedReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  maxDrawdownDate: string | null;
  winRate: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  avgHoldingDays: number;
  benchmarkReturn: number;
  alpha: number;
}

export interface BacktestTrade {
  ticker: string;
  entryDate: string;
  entryPrice: number;
  exitDate: string | null;
  exitPrice: number | null;
  shares: number;
  pnl: number;
  pnlPct: number;
  holdingDays: number;
}

export interface BacktestResult {
  summary: BacktestSummary;
  equityCurve: { date: string; value: number }[];
  benchmarkCurve: { date: string; value: number }[];
  monthlyReturns: { month: string; return: number }[];
  trades: BacktestTrade[];
}

export interface BacktestHistoryItem {
  id: number;
  strategyName: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  totalReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  createdAt: string;
}

export function useBacktest() {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<BacktestResult | null>(null);

  const historyQuery = useQuery({
    queryKey: ["backtest", "history"],
    queryFn: async () => {
      const data = await apiFetch<{ runs: BacktestHistoryItem[] }>("/api/invest/backtest/history");
      return data.runs ?? [];
    },
  });

  const mutation = useMutation({
    mutationFn: ({ startDate, endDate, initialCapital }: {
      startDate: string; endDate: string; initialCapital: number;
    }) =>
      apiFetch<BacktestResult>("/api/invest/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start_date: startDate, end_date: endDate, initial_capital: initialCapital }),
      }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["backtest", "history"] });
    },
  });

  return {
    result,
    history: historyQuery.data ?? [],
    loading: mutation.isPending,
    error: mutation.error?.message ?? null,
    runBacktest: (startDate: string, endDate: string, initialCapital: number) => {
      setResult(null);
      return mutation.mutateAsync({ startDate, endDate, initialCapital });
    },
    fetchHistory: () => historyQuery.refetch(),
  };
}
