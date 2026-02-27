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

export interface PortfolioResponse {
  positions: Position[];
  totalValue: number;
  dayPnl: number;
  dayPnlPct: number;
  cash: number;
  alerts: Alert[];
  performance?: PortfolioPerformance;
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

export interface RecommendationsResponse {
  items: Recommendation[];
  groupedByVerdict: Record<string, Recommendation[]>;
  totalCount: number;
}

export interface ClosedPositionsResponse {
  closedPositions: ClosedPosition[];
  totalRealizedPnl: number;
}

export type HealthResponse = SystemHealth;
