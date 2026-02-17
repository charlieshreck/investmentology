export const verdictColor: Record<string, string> = {
  STRONG_BUY: "var(--color-success)",
  BUY: "var(--color-success)",
  ACCUMULATE: "#4ade80",
  HOLD: "var(--color-warning)",
  WATCHLIST: "var(--color-text-muted)",
  REDUCE: "var(--color-warning)",
  SELL: "var(--color-error)",
  AVOID: "var(--color-error)",
  DISCARD: "var(--color-error)",
};

export const verdictLabel: Record<string, string> = {
  STRONG_BUY: "Strong Buy",
  BUY: "Buy",
  ACCUMULATE: "Accumulate",
  HOLD: "Hold",
  WATCHLIST: "Watchlist",
  REDUCE: "Reduce",
  SELL: "Sell",
  AVOID: "Avoid",
  DISCARD: "Discard",
};

export const verdictBadgeVariant: Record<string, "success" | "warning" | "error" | "neutral" | "accent"> = {
  STRONG_BUY: "success",
  BUY: "success",
  ACCUMULATE: "success",
  HOLD: "warning",
  WATCHLIST: "neutral",
  REDUCE: "warning",
  SELL: "error",
  AVOID: "error",
  DISCARD: "error",
};
