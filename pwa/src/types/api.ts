import type {
  Position,
  Decision,
  WatchlistItem,
  QuantGateRun,
  CalibrationBucket,
  SystemHealth,
  Alert,
  Recommendation,
  ClosedPosition,
} from "./models";

export interface ApiResponse<T> {
  data: T;
  timestamp: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  timestamp: string;
}

export interface PortfolioPerformance {
  alphaPct: number;
  sharpeRatio: number | null;
  sortinoRatio: number | null;
  winRate: number;
  maxDrawdownPct: number;
}

export interface DividendSummary {
  totalAnnual: number;
  totalMonthly: number;
  yield: number;
}

export interface PortfolioPerformanceExtended extends PortfolioPerformance {
  portfolioReturnPct?: number;
  spyReturnPct?: number;
  avgWinPct?: number;
  avgLossPct?: number;
  totalTrades?: number;
  expectancy?: number;
  dispositionRatio?: number;
  avgWinnerHoldDays?: number;
  avgLoserHoldDays?: number;
  measurementDays?: number;
}

export interface PortfolioResponse {
  positions: Position[];
  totalValue: number;
  dayPnl: number;
  dayPnlPct: number;
  cash: number;
  alerts: Alert[];
  performance?: PortfolioPerformanceExtended;
  dividendSummary?: DividendSummary;
}

export interface QuantGateResponse {
  latestRun: QuantGateRun;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  groupedByState: Record<string, WatchlistItem[]>;
}

export interface DecisionsResponse {
  decisions: Decision[];
  total: number;
  page: number;
  pageSize: number;
}

export interface CalibrationResponse {
  buckets: CalibrationBucket[];
  brierScore: number;
  totalPredictions: number;
}

export interface AnalyseRequest {
  ticker: string;
}

export interface AnalyseResponse {
  taskId: string;
  status: "queued" | "running" | "complete" | "error";
}

export interface RiskAllocation {
  current_pct: number;
  ideal_pct: number;
  gap_pct: number;
  status: "underweight" | "overweight" | "slightly_overweight" | "slightly_underweight" | "balanced" | "empty";
}

export interface PortfolioGaps {
  totalValue: number;
  positionCount: number;
  riskAllocations: Record<string, RiskAllocation>;
  sectorAllocations: Record<string, number>;
  underweightCategories: string[];
  overweightCategories: string[];
  concentrationWarnings: string[];
}

export interface AllocationGuidance {
  regime: string;
  stance: string;
  equityTargetMin: number;
  equityTargetMax: number;
  cashTargetMin: number;
  cashTargetMax: number;
  entryCriteria: string;
  summary: string;
}

export interface RecommendationsResponse {
  items: Recommendation[];
  groupedByVerdict: Record<string, Recommendation[]>;
  totalCount: number;
  portfolioGaps?: PortfolioGaps;
  allocationGuidance?: AllocationGuidance;
}

export interface ClosedPositionsResponse {
  closedPositions: ClosedPosition[];
  totalRealizedPnl: number;
}

export type HealthResponse = SystemHealth;
