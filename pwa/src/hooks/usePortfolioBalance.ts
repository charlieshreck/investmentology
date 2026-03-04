import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";

export interface BalanceData {
  sectors: Array<{ name: string; pct: number; zone: string; color: string; softMax: number; warnMax: number; tickers: string[] }>;
  riskCategories: Array<{ name: string; pct: number; zone: string; idealMin: number; idealMax: number; warnMax: number }>;
  positionCount: number;
  sectorCount: number;
  health: string;
  insights: string[];
}

export function usePortfolioBalance(positionCount: number) {
  return useQuery({
    queryKey: ["portfolio", "balance"],
    queryFn: () => apiFetch<BalanceData>("/portfolio/balance"),
    enabled: positionCount > 0,
  });
}
