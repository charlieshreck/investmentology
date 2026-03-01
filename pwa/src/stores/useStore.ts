import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  Position,
  Alert,
  WatchlistItem,
  QuantGateRun,
  QuantGateResult,
  AnalysisProgress,
} from "../types/models";

interface PortfolioPerformance {
  alphaPct: number;
  sharpeRatio: number | null;
  sortinoRatio: number | null;
  winRate: number;
  maxDrawdownPct: number;
}

interface PortfolioSlice {
  positions: Position[];
  totalValue: number;
  dayPnl: number;
  dayPnlPct: number;
  cash: number;
  alerts: Alert[];
  performance: PortfolioPerformance | null;
  setPortfolio: (data: {
    positions: Position[];
    totalValue: number;
    dayPnl: number;
    dayPnlPct: number;
    cash: number;
    alerts: Alert[];
    performance?: PortfolioPerformance;
  }) => void;
}

interface WatchlistSlice {
  items: WatchlistItem[];
  groupedByState: Record<string, WatchlistItem[]>;
  setWatchlist: (
    items: WatchlistItem[],
    grouped: Record<string, WatchlistItem[]>,
  ) => void;
}

interface QuantGateSlice {
  latestRun: QuantGateRun | null;
  topResults: QuantGateResult[];
  setQuantGate: (run: QuantGateRun) => void;
}

export interface ScreenerProgress {
  stage: string;
  detail: string;
  pct: number;
}

export interface CompletedAnalysis {
  ticker: string;
  decisionType: string;
  confidence: number;
  reasoning: string;
  agentStances?: AnalysisProgress["agentStances"];
  riskFlags?: string[];
  consensusScore?: number | null;
  completedAt: string;
}

interface UiSlice {
  activeView: string;
  overlayTicker: string | null;
  analysisProgress: AnalysisProgress | null;
  screenerProgress: ScreenerProgress | null;
  recentAnalyses: CompletedAnalysis[];
  setActiveView: (view: string) => void;
  setOverlayTicker: (ticker: string | null) => void;
  setAnalysisProgress: (progress: AnalysisProgress | null | ((prev: AnalysisProgress | null) => AnalysisProgress | null)) => void;
  setScreenerProgress: (progress: ScreenerProgress | null) => void;
  pushRecentAnalysis: (analysis: CompletedAnalysis) => void;
}

type AppState = PortfolioSlice & WatchlistSlice & QuantGateSlice & UiSlice;

export const useStore = create<AppState>()(persist((set) => ({
  // Portfolio
  positions: [],
  totalValue: 0,
  dayPnl: 0,
  dayPnlPct: 0,
  cash: 0,
  alerts: [],
  performance: null,
  setPortfolio: (data) =>
    set({
      positions: data.positions,
      totalValue: data.totalValue,
      dayPnl: data.dayPnl,
      dayPnlPct: data.dayPnlPct,
      cash: data.cash,
      alerts: data.alerts,
      performance: data.performance ?? null,
    }),

  // Watchlist
  items: [],
  groupedByState: {},
  setWatchlist: (items, grouped) =>
    set({ items, groupedByState: grouped }),

  // Quant Gate
  latestRun: null,
  topResults: [],
  setQuantGate: (run) =>
    set({ latestRun: run, topResults: run.results }),

  // UI
  activeView: "portfolio",
  overlayTicker: null,
  analysisProgress: null,
  screenerProgress: null,
  recentAnalyses: [],
  setActiveView: (view) => set({ activeView: view }),
  setOverlayTicker: (ticker) => set({ overlayTicker: ticker }),
  setAnalysisProgress: (progress) =>
    set((state) => ({
      analysisProgress:
        typeof progress === "function"
          ? progress(state.analysisProgress)
          : progress,
    })),
  setScreenerProgress: (progress) => set({ screenerProgress: progress }),
  pushRecentAnalysis: (analysis) =>
    set((state) => ({
      recentAnalyses: [
        analysis,
        ...state.recentAnalyses.filter((a) => a.ticker !== analysis.ticker),
      ].slice(0, 20),
    })),
}), {
  name: "investmentology-store",
  partialize: (state) => ({ recentAnalyses: state.recentAnalyses }),
}));
