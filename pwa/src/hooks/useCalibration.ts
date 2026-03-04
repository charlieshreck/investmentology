import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { CalibrationResponse } from "../types/api";

export function useCalibration() {
  const query = useQuery({
    queryKey: ["calibration"],
    queryFn: () => apiFetch<CalibrationResponse>("/api/invest/learning/calibration"),
  });

  return {
    buckets: query.data?.buckets ?? [],
    brierScore: query.data?.brierScore ?? null,
    totalPredictions: query.data?.totalPredictions ?? 0,
    loading: query.isLoading,
    error: query.error?.message ?? null,
  };
}
