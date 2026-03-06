import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../utils/apiClient";

interface TriggerAgentResult {
  status: string;
  agent: string;
  ticker: string;
  confidence?: number;
  signalId?: number;
  stepId?: number;
  action?: string;
  estimatedWaitSeconds?: number;
}

interface TriggerBoardResult {
  status: string;
  ticker: string;
  verdictId: number;
  adjustedVerdict?: string;
  opinions?: unknown[];
  narrative?: unknown;
}

interface TriggerFullResult {
  results: Array<{
    ticker: string;
    status: string;
    forceDataRefresh: boolean;
  }>;
}

export function useTriggerAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { ticker: string; agent: string }) =>
      apiFetch<TriggerAgentResult>("/api/invest/pipeline/trigger/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["pipeline", "data-report", vars.ticker] });
      qc.invalidateQueries({ queryKey: ["pipeline", "ticker", vars.ticker] });
    },
  });
}

export function useTriggerBoard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { ticker: string; verdict_id?: number }) =>
      apiFetch<TriggerBoardResult>("/api/invest/pipeline/trigger/board", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["pipeline", "data-report", vars.ticker] });
      qc.invalidateQueries({ queryKey: ["stock", vars.ticker] });
    },
  });
}

export function useTriggerFull() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { tickers: string[]; force_data_refresh?: boolean }) =>
      apiFetch<TriggerFullResult>("/api/invest/pipeline/trigger/full", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline"] });
    },
  });
}
