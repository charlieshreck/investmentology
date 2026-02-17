import { useState, useCallback } from "react";

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
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [history, setHistory] = useState<BacktestHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = useCallback(async (startDate: string, endDate: string, initialCapital: number) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/invest/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start_date: startDate, end_date: endDate, initial_capital: initialCapital }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backtest failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch("/api/invest/backtest/history");
      if (res.ok) {
        const data = await res.json();
        setHistory(data.runs || []);
      }
    } catch {
      // ignore
    }
  }, []);

  return { result, history, loading, error, runBacktest, fetchHistory };
}
