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
  entryDate?: string;
  positionType?: string;
  name?: string;
  priceUnavailable?: boolean;
  dividendPerShare?: number;
  dividendYield?: number;
  annualDividend?: number;
  monthlyDividend?: number;
  dividendFrequency?: string;
  exDividendDate?: string | null;
}

export interface EarningsMomentum {
  score: number;
  label: string;
  upwardRevisions: number;
  downwardRevisions: number;
  beatStreak: number;
}

export interface PortfolioFit {
  score: number;
  reasoning: string;
  diversificationScore: number;
  balanceScore: number;
  capacityScore: number;
  alreadyHeld: boolean;
}

export interface HeldPosition {
  positionType: string;
  daysHeld: number;
  pnlPct: number;
  entryPrice: number;
  thesisHealth: string;
  convictionTrend: number;
  entryThesis: string;
  reasoning: string;
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
  consensusTier: string | null;
  reasoning: string | null;
  agentStances: AgentStance[] | null;
  riskFlags: string[] | null;
  auditorOverride: boolean;
  mungerOverride: boolean;
  analysisDate: string | null;
  successProbability: number | null;
  stabilityScore?: number;
  stabilityLabel?: string;
  buzzScore?: number;
  buzzLabel?: string;
  headlineSentiment?: number;
  contrarianFlag?: boolean;
  earningsMomentum?: EarningsMomentum;
  portfolioFit?: PortfolioFit;
  dividendYield?: number;
  changePct?: number;
  suggestedType?: string;
  suggestedLabel?: string;
  heldPosition?: HeldPosition;
  advisoryOpinions?: AdvisoryOpinion[] | null;
  boardNarrative?: BoardNarrative | null;
  boardAdjustedVerdict?: string | null;
  dataSourceCount?: number;
  dataSourceTotal?: number;
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
  advisoryOpinions?: AdvisoryOpinion[] | null;
  boardNarrative?: BoardNarrative | null;
  boardAdjustedVerdict?: string | null;
}

export interface WatchlistBlockingFactor {
  tag: string;
  label: string;
  source: string;
}

export interface WatchlistGraduationCriteria {
  tag: string;
  label: string;
  met: boolean;
}

export interface WatchlistMeta {
  reason: string | null;
  blockingFactors: WatchlistBlockingFactor[];
  graduationCriteria: WatchlistGraduationCriteria[];
  graduationTrigger: string | null;
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
  watchlistMeta?: WatchlistMeta;
  targetEntryPrice?: number | null;
  qgRank?: number | null;
  nextCatalystDate?: string | null;
  daysOnWatchlist?: number | null;
  convictionTrend?: string | null;
  distanceToEntry?: number | null;
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

export interface AnalysisAgentStance {
  name: string;
  sentiment: number;
  confidence: number;
  key_signals: string[];
  summary: string;
}

export interface AdvisoryOpinion {
  advisor_name: string;
  display_name: string;
  vote: string;
  confidence: number;
  assessment: string;
  key_concern: string | null;
  key_endorsement: string | null;
  reasoning: string;
}

export interface BoardNarrative {
  headline: string;
  narrative: string;
  risk_summary: string;
  pre_mortem: string;
  conflict_resolution: string;
  advisor_consensus: Record<string, unknown>;
}

export interface KillScenario {
  scenario: string;
  likelihood: "low" | "medium" | "high";
  impact: "moderate" | "severe" | "fatal";
  timeframe: string;
}

export interface PreMortem {
  narrative: string;
  key_risks: string[];
  probability_estimate: string;
}

export interface AdversarialResult {
  verdict: "PROCEED" | "CAUTION" | "VETO";
  kill_scenarios: KillScenario[];
  premortem: PreMortem | null;
  bias_flags: { bias_name: string; is_flagged: boolean; detail: string }[];
  reasoning: string;
}

export interface TargetPriceRange {
  prices: { agent: string; price: number }[];
  low: number;
  high: number;
  median: number;
}

export interface AnalysisProgress {
  ticker: string;
  steps: PipelineStep[];
  currentStep: number;
  tickerIndex?: number;
  tickerTotal?: number;
  errorMessage?: string;
  result?: Decision;
  agentStances?: AnalysisAgentStance[];
  riskFlags?: string[];
  consensusScore?: number | null;
  advisoryOpinions?: AdvisoryOpinion[];
  boardNarrative?: BoardNarrative;
  boardAdjustedVerdict?: string;
}

export interface SystemHealth {
  status: "healthy" | "degraded" | "down";
  database: boolean;
  apiKeys: Record<string, boolean>;
  lastQuantRun?: string;
  decisionsLogged: number;
  uptime: number;
}

// Pipeline controller state types

export interface PipelineCycle {
  id: string;
  startedAt: string;
  tickerCount: number;
  status: "active" | "completed" | "expired";
}

export interface PipelineStatus {
  cycle: PipelineCycle | null;
  steps: Record<string, number>;
}

export interface PipelineTickerPreFilter {
  passed: boolean;
  reason: string | null;
  rulesFailed: string[];
}

export interface PipelineTickerSummary {
  ticker: string;
  total_steps: number;
  completed: number;
  failed: number;
  running: number;
  pending: number;
  preFilter?: PipelineTickerPreFilter;
  gateOutcome?: "pre_filtered" | "passed" | "rejected" | null;
}

export interface PipelineStepDetail {
  step: string;
  status: "pending" | "running" | "completed" | "failed" | "expired";
  startedAt: string | null;
  completedAt: string | null;
  error: string | null;
  retryCount: number;
}

export interface PipelineScreenerVerdict {
  name: string;
  verdict: "pass" | "reject";
  confidence: number | null;
  tags: string[];
  latencyMs: number | null;
}

export interface PipelineScreenerVotes {
  pass: number;
  reject: number;
  total: number;
  required: number;
}

export interface PipelineTickerDetail {
  ticker: string;
  steps: PipelineStepDetail[];
  preFilter: {
    passed: boolean;
    reason: string | null;
    rulesChecked: number;
    rulesFailed: string[];
  } | null;
  screeners: PipelineScreenerVerdict[];
  gateOutcome: "pre_filtered" | "passed" | "rejected" | null;
  screenerVotes: PipelineScreenerVotes | null;
}

export interface PipelineFunnelStages {
  dataFetch: { completed: number; failed: number; pending: number; running: number };
  preFilter: { completed: number; pending: number; passed: number; rejected: number; reasons: Record<string, number> };
  screeners: { stats: Record<string, Record<string, number>>; totalScreenerSteps: number };
  gate: { completed: number; pending: number; passed: number; rejected: number; preFiltered: number };
  analysis: { tickers: number; completed: number; running: number; pending: number; failed: number };
}

export interface PipelineFunnel {
  hasCycle: boolean;
  cycleId?: string;
  startedAt?: string;
  totalTickers?: number;
  stages?: PipelineFunnelStages;
}

export interface PipelineStepHealth {
  step: string;
  total: number;
  completed: number;
  failed: number;
  errorRate: number;
}

export interface PipelineStepTiming {
  step: string;
  avgSeconds: number;
  maxSeconds: number;
  count: number;
}

export interface PipelineRecentError {
  ticker: string;
  step: string;
  error: string | null;
  at: string | null;
  retries: number;
}

export interface PipelineHealth {
  hasCycle: boolean;
  cycleId?: string;
  stepHealth?: PipelineStepHealth[];
  stepTiming?: PipelineStepTiming[];
  recentErrors?: PipelineRecentError[];
  reentryBlocks?: { total: number; active: number };
}

// ── Data Report Types ──────────────────────────────────────────────────

export interface DataReportAgentImpact {
  agent: string;
  status: "ok" | "capped";
  cap?: number;
  reason?: string;
  missingOptional: string[];
  lastSignalAt?: string;
  lastConfidence?: number | null;
}

export interface DataReport {
  ticker: string;
  dataAge: Record<string, string>;
  available: Record<string, boolean>;
  agentImpact: DataReportAgentImpact[];
  cappedAgentCount: number;
  totalAgentCount: number;
}

// ── Analysis Overview (command center) ────────────────────────────────────

export interface AnalysisOverviewAgent {
  name: string;
  confidence: number | null;
  ranAt: string;
  status: "ok" | "capped";
}

export interface AnalysisOverviewTicker {
  ticker: string;
  category: "portfolio" | "watchlist" | "recommendation" | "other";
  verdict: string | null;
  verdictConfidence: number | null;
  verdictAt: string | null;
  boardAdjustedVerdict: string | null;
  dataSourceCount: number;
  dataSourceTotal: number;
  dataStaleness: "fresh" | "partial" | "stale" | "missing";
  lastAgentRun: string | null;
  agentCount: number;
  agentTotal: number;
  agents: AnalysisOverviewAgent[];
  available: Record<string, boolean>;
  dataAge: Record<string, string>;
  cappedAgentCount: number;
}
