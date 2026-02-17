import { useEffect, useState } from "react";
import type { CalibrationBucket } from "../types/models";
import type { CalibrationResponse } from "../types/api";

export function useCalibration() {
  const [buckets, setBuckets] = useState<CalibrationBucket[]>([]);
  const [brierScore, setBrierScore] = useState<number | null>(null);
  const [totalPredictions, setTotalPredictions] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchCalibration() {
      try {
        setLoading(true);
        const res = await fetch("/api/invest/learning/calibration");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: CalibrationResponse = await res.json();
        if (!cancelled) {
          setBuckets(data.buckets);
          setBrierScore(data.brierScore);
          setTotalPredictions(data.totalPredictions);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchCalibration();
    return () => { cancelled = true; };
  }, []);

  return { buckets, brierScore, totalPredictions, loading, error };
}
