/**
 * Shared formatting + visual helpers extracted from StockDeepDive.tsx.
 * Used by all deepdive sub-components.
 */

export function formatCap(cap: number): string {
  if (!cap) return "—";
  if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`;
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`;
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(0)}M`;
  return `$${cap.toLocaleString()}`;
}

export function formatNum(n: number): string {
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

export function formatVol(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toLocaleString();
}

export function sentimentBar(sentiment: number) {
  const pct = Math.round((sentiment + 1) * 50);
  const color = sentiment > 0.1 ? "var(--color-success)" : sentiment < -0.1 ? "var(--color-error)" : "var(--color-warning)";
  return { pct, color };
}

export function voteColor(vote: string): string {
  if (vote === "APPROVE") return "var(--color-success)";
  if (vote === "VETO") return "var(--color-error)";
  if (vote === "ADJUST_UP") return "var(--color-accent-bright)";
  if (vote === "ADJUST_DOWN") return "var(--color-warning)";
  return "var(--color-text-muted)";
}

export function voteLabel(vote: string): string {
  return vote.replace(/_/g, " ");
}
