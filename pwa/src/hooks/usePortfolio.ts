import { useCallback, useEffect, useState } from "react";
import { useStore } from "../stores/useStore";
import type { PortfolioResponse, ClosedPositionsResponse } from "../types/api";
import type { ClosedPosition } from "../types/models";

export function usePortfolio() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [closedPositions, setClosedPositions] = useState<ClosedPosition[]>([]);
  const [totalRealizedPnl, setTotalRealizedPnl] = useState(0);
  const setPortfolio = useStore((s) => s.setPortfolio);
  const positions = useStore((s) => s.positions);
  const totalValue = useStore((s) => s.totalValue);
  const dayPnl = useStore((s) => s.dayPnl);
  const dayPnlPct = useStore((s) => s.dayPnlPct);
  const cash = useStore((s) => s.cash);
  const alerts = useStore((s) => s.alerts);

  const fetchPortfolio = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/invest/portfolio");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PortfolioResponse = await res.json();
      setPortfolio(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [setPortfolio]);

  const fetchClosed = useCallback(async () => {
    try {
      const res = await fetch("/api/invest/portfolio/closed");
      if (!res.ok) return;
      const data: ClosedPositionsResponse = await res.json();
      setClosedPositions(data.closedPositions);
      setTotalRealizedPnl(data.totalRealizedPnl);
    } catch {
      // silent — closed positions are secondary
    }
  }, []);

  useEffect(() => {
    fetchPortfolio();
    fetchClosed();
  }, [fetchPortfolio, fetchClosed]);

  const addPosition = useCallback(async (data: {
    ticker: string;
    entry_price: number;
    shares: number;
    position_type?: string;
    weight?: number;
    stop_loss?: number | null;
    fair_value_estimate?: number | null;
    thesis?: string;
  }) => {
    const res = await fetch("/api/invest/portfolio/positions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await fetchPortfolio();
    return res.json();
  }, [fetchPortfolio]);

  const closePosition = useCallback(async (positionId: number, exitPrice: number) => {
    const res = await fetch(`/api/invest/portfolio/positions/${positionId}/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exit_price: exitPrice }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await fetchPortfolio();
    await fetchClosed();
    return res.json();
  }, [fetchPortfolio, fetchClosed]);

  return {
    positions, totalValue, dayPnl, dayPnlPct, cash, alerts,
    closedPositions, totalRealizedPnl,
    loading, error,
    refetch: fetchPortfolio,
    addPosition, closePosition,
  };
}
