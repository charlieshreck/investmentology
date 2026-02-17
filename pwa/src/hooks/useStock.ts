import { useEffect, useState } from "react";
import type { Stock } from "../types/models";

export function useStock(ticker: string | undefined) {
  const [stock, setStock] = useState<Stock | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;
    async function fetchStock() {
      try {
        setLoading(true);
        const res = await fetch(`/api/invest/stock/${ticker}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: Stock = await res.json();
        if (!cancelled) {
          setStock(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchStock();
    return () => { cancelled = true; };
  }, [ticker]);

  return { stock, loading, error };
}
