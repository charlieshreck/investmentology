import { QueryClient } from "@tanstack/react-query";

const API_BASE = "/api/invest";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
});

/** Centralized fetch with 401 interception (replaces window.fetch monkey-patch). */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("/") ? path : `${API_BASE}/${path}`;
  const res = await fetch(url, init);

  if (res.status === 401 && !url.includes("/auth/")) {
    window.location.reload();
    // Never resolves — page is reloading
    return new Promise(() => {});
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }

  return res.json();
}
