import { create } from "zustand";
import type {
  Position,
  Alert,
  WatchlistItem,
  QuantGateRun,
  QuantGateResult,
  AnalysisProgress,
} from "../types/models";

interface PortfolioPerformance {
  spyAlpha: number;
  sharpeRatio: number;
  sortinoRatio: number;
  winRate: number;
  maxDrawdown: number;
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

interface UiSlice {
  activeView: string;
  overlayTicker: string | null;
  analysisProgress: AnalysisProgress | null;
  setActiveView: (view: string) => void;
  setOverlayTicker: (ticker: string | null) => void;
  setAnalysisProgress: (progress: AnalysisProgress | null | ((prev: AnalysisProgress | null) => AnalysisProgress | null)) => void;
}

type AppState = PortfolioSlice & WatchlistSlice & QuantGateSlice & UiSlice;

export const useStore = create<AppState>((set) => ({
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
  setActiveView: (view) => set({ activeView: view }),
  setOverlayTicker: (ticker) => set({ overlayTicker: ticker }),
  setAnalysisProgress: (progress) =>
    set((state) => ({
      analysisProgress:
        typeof progress === "function"
          ? progress(state.analysisProgress)
          : progress,
    })),
}));
