import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";
import type { Recommendation } from "../types/models";

// --- Daily Briefing Summary ---

export interface PendulumComponents {
  vix: number | null;
  creditSpread: number | null;
  putCall: number | null;
  momentum: number | null;
}

export interface BriefingSummary {
  date: string;
  pendulumScore: number;
  pendulumLabel: string;
  pendulumComponents?: PendulumComponents | null;
  sizingMultiplier?: number | null;
  macroSignals?: string[];
  positionCount: number;
  totalValue: number;
  totalUnrealizedPnl: number;
  newRecommendationCount: number;
  alertCount: number;
  criticalAlertCount: number;
  overallRiskLevel: string;
  topActions: {
    priority: number;
    category: string;
    ticker: string | null;
    action: string;
  }[];
}

export function useDailyBriefing() {
  const query = useQuery({
    queryKey: ["daily", "briefing"],
    queryFn: () => apiFetch<BriefingSummary>("/api/invest/daily/briefing/summary"),
  });

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
}

// --- Portfolio Advisor Actions ---

export interface AgentStanceSummary {
  agent: string;
  sentiment: number;
  confidence: number;
  summary: string;
}

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
  agent_summary?: AgentStanceSummary[];
  consensus_score?: number;
}

export function usePortfolioAdvisor() {
  const query = useQuery({
    queryKey: ["portfolio", "advisor"],
    queryFn: () => apiFetch<{ actions: AdvisorAction[] }>("/api/invest/portfolio/advisor"),
  });

  return {
    actions: query.data?.actions ?? [],
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
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
  const query = useQuery({
    queryKey: ["portfolio", "thesis-summary"],
    queryFn: () => apiFetch<{ positions: ThesisPosition[] }>("/api/invest/portfolio/thesis-summary"),
  });

  return {
    positions: query.data?.positions ?? [],
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
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
  const query = useQuery({
    queryKey: ["portfolio", "risk-snapshot"],
    queryFn: () => apiFetch<RiskSnapshot>("/api/invest/portfolio/risk-snapshot"),
  });

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
    refresh: () => query.refetch(),
  };
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
  const query = useQuery({
    queryKey: ["learning", "attribution"],
    queryFn: () => apiFetch<AttributionReport>("/api/invest/learning/attribution"),
  });

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: query.error?.message ?? null,
  };
}

// --- Top Recommendations (for Today page) ---

const POSITIVE_VERDICTS = new Set(["STRONG_BUY", "BUY", "ACCUMULATE"]);

export function useTopRecommendations(limit = 3) {
  const query = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => apiFetch<{ items: Recommendation[] }>("/api/invest/recommendations"),
  });

  const all = query.data?.items ?? [];
  const positive = all
    .filter((r) => POSITIVE_VERDICTS.has(r.verdict))
    .sort((a, b) => (b.successProbability ?? 0) - (a.successProbability ?? 0));

  return {
    items: positive.slice(0, limit),
    totalNew: positive.length,
    loading: query.isLoading,
  };
}
