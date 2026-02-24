export interface Position {
  id?: number;
  ticker: string;
  shares: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  dayChange: number;
  dayChangePct: number;
  weight: number;
}

export interface Recommendation {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  currentPrice: number;
  marketCap: number;
  watchlistState: string | null;
  verdict: string;
  confidence: number | null;
  consensusScore: number | null;
  reasoning: string | null;
  agentStances: AgentStance[] | null;
  riskFlags: string[] | null;
  auditorOverride: boolean;
  mungerOverride: boolean;
  analysisDate: string | null;
  successProbability: number | null;
}

export interface AgentStance {
  name: string;
  sentiment: number;
  confidence: number;
  key_signals: string[];
  summary: string;
}

export interface ClosedPosition {
  id: number;
  ticker: string;
  entryDate: string;
  entryPrice: number;
  exitDate: string | null;
  exitPrice: number | null;
  shares: number;
  realizedPnl: number;
  realizedPnlPct: number;
  holdingDays: number | null;
}

export interface Stock {
  ticker: string;
  name: string;
  sector: string;
  marketCap: number;
  price: number;
  roic: number;
  earningsYield: number;
  magicFormulaRank: number;
}

export interface Decision {
  id: string;
  ticker: string;
  decisionType: string;
  confidence: number;
  reasoning: string;
  createdAt: string;
  layer: string;
  outcome?: string;
  settledAt?: string;
}

export interface Signal {
  ticker: string;
  signalType: "BUY" | "SELL" | "TRIM" | "HOLD";
  confidence: number;
  source: string;
  timestamp: string;
}

export interface Alert {
  id: string;
  severity: "info" | "warning" | "error" | "critical";
  title: string;
  message: string;
  ticker?: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface WatchlistVerdict {
  recommendation: string;
  confidence: number | null;
  consensusScore: number | null;
  reasoning: string | null;
  agentStances: unknown[] | null;
  riskFlags: string[] | null;
  verdictDate: string | null;
}

export interface WatchlistItem {
  ticker: string;
  name: string;
  sector: string;
  state: string;
  addedAt: string;
  lastAnalysis?: string | null;
  priceAtAdd: number;
  currentPrice: number;
  marketCap: number;
  compositeScore: number | null;
  piotroskiScore: number | null;
  altmanZone: "safe" | "grey" | "distress" | null;
  combinedRank: number | null;
  altmanZScore: number | null;
  verdict: WatchlistVerdict | null;
  notes?: string;
  successProbability: number | null;
  changePct?: number;
  priceHistory?: { date: string; price: number }[];
}

export interface QuantGateResult {
  ticker: string;
  name: string;
  roicRank: number;
  eyRank: number;
  combinedRank: number;
  roic: number;
  earningsYield: number;
  piotroskiScore: number;
  altmanZScore: number | null;
  altmanZone: "safe" | "grey" | "distress" | null;
  compositeScore: number | null;
  marketCap: number;
  sector: string;
  verdict: string | null;
  verdictConfidence: number | null;
  verdictDate: string | null;
}

export interface QuantGateRun {
  id: string;
  runDate: string;
  stocksScreened: number;
  stocksPassed: number;
  analyzedCount: number;
  results: QuantGateResult[];
}

export interface CalibrationBucket {
  midpoint: number;
  accuracy: number;
  count: number;
}

export interface PipelineStep {
  label: string;
  status: "pending" | "active" | "done" | "error";
}

export interface AnalysisProgress {
  ticker: string;
  steps: PipelineStep[];
  currentStep: number;
  result?: Decision;
}

export interface SystemHealth {
  status: "healthy" | "degraded" | "down";
  database: boolean;
  apiKeys: Record<string, boolean>;
  lastQuantRun?: string;
  decisionsLogged: number;
  uptime: number;
}
