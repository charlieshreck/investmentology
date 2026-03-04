import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { Stock } from "../types/models";

export function useStock(ticker: string | undefined) {
  const query = useQuery({
    queryKey: ["stock", ticker],
    queryFn: () => apiFetch<Stock>(`/api/invest/stock/${ticker}`),
    enabled: !!ticker,
  });

  return {
    stock: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
  };
}
