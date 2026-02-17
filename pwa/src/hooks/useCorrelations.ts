import { useState, useEffect } from "react";

export interface Correlation {
  ticker1: string;
  ticker2: string;
  value: number;
}

interface CorrelationData {
  tickers: string[];
  correlations: Correlation[];
}

export function useCorrelations(positionCount: number, tickerFingerprint: string) {
  const [data, setData] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (positionCount < 2) {
      setData(null);
      return;
    }

    setLoading(true);
    fetch("/api/invest/portfolio/correlations")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [positionCount, tickerFingerprint]);

  return { data, loading };
}
