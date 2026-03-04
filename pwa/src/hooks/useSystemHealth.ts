import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { SystemHealth } from "../types/models";

export function useSystemHealth() {
  const query = useQuery({
    queryKey: ["system", "health"],
    queryFn: () => apiFetch<SystemHealth>("/api/invest/system/health"),
  });

  return {
    health: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
  };
}
