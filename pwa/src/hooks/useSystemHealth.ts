import { useEffect, useState } from "react";
import type { SystemHealth } from "../types/models";

export function useSystemHealth() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchHealth() {
      try {
        setLoading(true);
        const res = await fetch("/api/invest/system/health");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: SystemHealth = await res.json();
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchHealth();
    return () => { cancelled = true; };
  }, []);

  return { health, loading, error };
}
