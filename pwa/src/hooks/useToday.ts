import { useCallback, useEffect, useState } from "react";

// --- Daily Briefing Summary ---

export interface BriefingSummary {
  date: string;
  pendulumScore: number;
  pendulumLabel: string;
  sizingMultiplier: number;
  positionCount: number;
  totalValue: number;
  alertCounts: { critical: number; high: number; medium: number };
  topActions: {
    type: string;
    ticker: string | null;
    priority: string;
    title: string;
    detail: string;
    reasoning: string;
  }[];
}

export function useDailyBriefing() {
  const [data, setData] = useState<BriefingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/invest/daily/briefing/summary");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { data, loading, error, refresh };
}

// --- Portfolio Advisor Actions ---

export interface AdvisorAction {
  type: string;
  ticker: string | null;
  priority: string;
  title: string;
  detail: string;
  reasoning: string;
  position_id?: number;
  current_shares?: number;
  current_price?: number;
  current_weight?: number;
}

export function usePortfolioAdvisor() {
  const [actions, setActions] = useState<AdvisorAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/invest/portfolio/advisor");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setActions(json.actions ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { actions, loading, error, refresh };
}

// --- Thesis Summary ---

export interface ThesisPosition {
  ticker: string;
  position_type: string;
  thesis_health: "INTACT" | "UNDER_REVIEW" | "CHALLENGED" | "BROKEN";
  entry_thesis: string;
  pnl_pct: number;
  days_held: number;
  conviction_trend: number;
  reasoning: string;
}

export function useThesisSummary() {
  const [positions, setPositions] = useState<ThesisPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/invest/portfolio/thesis-summary");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setPositions(json.positions ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { positions, loading, error, refresh };
}

// --- Portfolio Risk Snapshot ---

export interface RiskPosition {
  ticker: string;
  position_type: string;
  thesis_health: string;
  weight_pct: number;
  pnl_pct: number;
  days_held: number;
}

export interface RiskSnapshot {
  total_value: number;
  position_count: number;
  sector_concentration: Record<string, number>;
  top_position_weight: number;
  avg_thesis_health_score: number;
  risk_level: string;
  positions: RiskPosition[];
}

export function usePortfolioRisk() {
  const [data, setData] = useState<RiskSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/invest/portfolio/risk-snapshot");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { data, loading, error, refresh };
}

// --- Learning Attribution ---

export interface AgentAttribution {
  total_calls: number;
  accuracy: number;
  bullish_accuracy: number;
  bearish_accuracy: number;
  bullish_total: number;
  bearish_total: number;
}

export interface SignalPerf {
  agent: string;
  signal: string;
  accuracy: number;
}

export interface AttributionReport {
  status: string;
  message?: string;
  agents: Record<string, AgentAttribution>;
  recommended_weights: Record<string, number>;
  top_signals: SignalPerf[];
  worst_signals: SignalPerf[];
  recommendations: string[];
}

export function useAttribution() {
  const [data, setData] = useState<AttributionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/invest/learning/attribution");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return { data, loading, error };
}
