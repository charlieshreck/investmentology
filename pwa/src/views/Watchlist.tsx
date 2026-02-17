import { useCallback } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { useWatchlist } from "../hooks/useWatchlist";
import { useAnalyze } from "../hooks/useAnalyze";
import { useStore } from "../stores/useStore";
import { verdictColor, verdictLabel, verdictBadgeVariant } from "../utils/verdictHelpers";
import type { WatchlistItem } from "../types/models";

function stateVariant(state: string): "accent" | "success" | "warning" | "error" | "neutral" {
  const map: Record<string, "accent" | "success" | "warning" | "error" | "neutral"> = {
    UNIVERSE: "neutral",
    CANDIDATE: "neutral",
    ASSESSED: "accent",
    CONVICTION_BUY: "success",
    WATCHLIST_EARLY: "accent",
    WATCHLIST_CATALYST: "warning",
    POSITION_HOLD: "success",
    POSITION_TRIM: "warning",
    POSITION_SELL: "warning",
    CONFLICT_REVIEW: "error",
    REJECTED: "error",
  };
  return map[state] ?? "neutral";
}

function pnlColor(n: number): string {
  if (n > 0) return "var(--color-success)";
  if (n < 0) return "var(--color-error)";
  return "var(--color-text-secondary)";
}

function compositeBar(score: number | null) {
  if (score == null) return <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-xs)" }}>--</span>;
  const pct = Math.round(score * 100);
  const color =
    pct >= 70 ? "var(--color-success)" : pct >= 40 ? "var(--color-warning)" : "var(--color-error)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-xs)" }}>
      <div style={{ width: 36, height: 5, borderRadius: 3, background: "var(--color-surface-2)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: color }} />
      </div>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>{score.toFixed(2)}</span>
    </div>
  );
}

function fScoreBadge(score: number | null) {
  if (score == null) return null;
  const variant = score >= 7 ? "success" : score >= 4 ? "warning" : "error";
  return <Badge variant={variant}>F{score}</Badge>;
}

function zoneBadge(zone: string | null) {
  if (zone === "safe") return <Badge variant="success">Safe</Badge>;
  if (zone === "grey") return <Badge variant="warning">Grey</Badge>;
  if (zone === "distress") return <Badge variant="error">Dist</Badge>;
  return null;
}

function formatCap(cap: number): string {
  if (!cap) return "";
  if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`;
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`;
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(0)}M`;
  return `$${cap.toLocaleString()}`;
}

function ItemCard({
  item,
  onClick,
  onAnalyze,
  isAnalyzing,
}: {
  item: WatchlistItem;
  onClick: () => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
}) {
  const changePct = item.priceAtAdd > 0
    ? ((item.currentPrice - item.priceAtAdd) / item.priceAtAdd) * 100
    : 0;
  const hasVerdict = item.verdict != null;
  const vColor = hasVerdict ? verdictColor[item.verdict!.recommendation] ?? "var(--color-text-muted)" : undefined;
  const vLabel = hasVerdict ? verdictLabel[item.verdict!.recommendation] ?? item.verdict!.recommendation : undefined;
  const vVariant = hasVerdict ? verdictBadgeVariant[item.verdict!.recommendation] ?? "neutral" : undefined;

  return (
    <div
      onClick={onClick}
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto auto auto",
        alignItems: "center",
        gap: "var(--space-md)",
        padding: "var(--space-md)",
        borderRadius: "var(--radius-sm)",
        cursor: "pointer",
        transition: `background var(--duration-fast) var(--ease-out)`,
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-1)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
    >
      {/* Left: ticker / name / sector + scores */}
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
          <span style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{item.ticker}</span>
          {item.sector && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>{item.sector}</span>
          )}
        </div>
        <div style={{
          fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {item.name}
          {item.marketCap > 0 && ` · ${formatCap(item.marketCap)}`}
        </div>
        <div style={{ display: "flex", gap: "var(--space-xs)", marginTop: "var(--space-xs)", alignItems: "center" }}>
          {compositeBar(item.compositeScore)}
          {fScoreBadge(item.piotroskiScore)}
          {zoneBadge(item.altmanZone)}
          {item.combinedRank != null && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
              #{item.combinedRank}
            </span>
          )}
        </div>
      </div>

      {/* Verdict badge */}
      <div style={{ textAlign: "center", minWidth: 60 }}>
        {hasVerdict ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            <Badge variant={vVariant!}>{vLabel}</Badge>
            {item.verdict!.confidence != null && (
              <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: vColor }}>
                {(item.verdict!.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
        ) : (
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>--</span>
        )}
      </div>

      {/* Price */}
      <div style={{ textAlign: "right", minWidth: 60 }}>
        {item.currentPrice > 0 ? (
          <>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>
              ${item.currentPrice.toFixed(2)}
            </div>
            {item.priceAtAdd > 0 && (
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: pnlColor(changePct) }}>
                {changePct >= 0 ? "+" : ""}{changePct.toFixed(1)}%
              </div>
            )}
          </>
        ) : (
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>--</span>
        )}
      </div>

      {/* Analyze button */}
      <button
        onClick={(e) => { e.stopPropagation(); onAnalyze(); }}
        disabled={isAnalyzing}
        style={{
          padding: "var(--space-xs) var(--space-md)",
          fontSize: "var(--text-xs)",
          fontWeight: 600,
          background: isAnalyzing ? "var(--color-surface-2)" : "var(--color-accent-ghost)",
          color: isAnalyzing ? "var(--color-text-muted)" : "var(--color-accent-bright)",
          border: "none",
          borderRadius: "var(--radius-full)",
          cursor: isAnalyzing ? "wait" : "pointer",
          whiteSpace: "nowrap",
          fontFamily: "var(--font-sans)",
        }}
      >
        {isAnalyzing ? "..." : hasVerdict ? "Re-analyze" : "Analyze"}
      </button>
    </div>
  );
}

export function Watchlist() {
  const { groupedByState, loading, error, refetch } = useWatchlist();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const onAnalyzeComplete = useCallback((ticker: string) => {
    setOverlayTicker(ticker);
  }, [setOverlayTicker]);
  const { analyzing, triggerAnalysis } = useAnalyze(onAnalyzeComplete, refetch);

  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Watchlist" />
        <div style={{ padding: "var(--space-xl)" }}>
          <p style={{ color: "var(--color-text-muted)" }}>Loading watchlist...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Watchlist" />
        <div style={{ padding: "var(--space-xl)" }}>
          <BentoCard>
            <p style={{ color: "var(--color-error)" }}>Failed to load watchlist: {error}</p>
          </BentoCard>
        </div>
      </div>
    );
  }

  const states = Object.keys(groupedByState);
  const totalItems = states.reduce((s, k) => s + groupedByState[k].length, 0);
  const analyzedCount = states.reduce(
    (s, k) => s + groupedByState[k].filter((i) => i.verdict != null).length,
    0,
  );

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Watchlist"
        subtitle={`${totalItems} stocks · ${analyzedCount} analyzed`}
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* State summary badges */}
        <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
          {states.map((state) => {
            const stateAnalyzed = groupedByState[state].filter((i) => i.verdict != null).length;
            return (
              <Badge key={state} variant={stateVariant(state)}>
                {state.replace(/_/g, " ")} ({stateAnalyzed}/{groupedByState[state].length})
              </Badge>
            );
          })}
        </div>

        {/* Grouped items */}
        {states.map((state) => (
          <BentoCard key={state} title={state.replace(/_/g, " ")}>
            <div style={{ display: "flex", flexDirection: "column" }}>
              {groupedByState[state].map((item) => (
                <ItemCard
                  key={item.ticker}
                  item={item}
                  onClick={() => setOverlayTicker(item.ticker)}
                  onAnalyze={() => triggerAnalysis(item.ticker)}
                  isAnalyzing={analyzing.has(item.ticker)}
                />
              ))}
            </div>
          </BentoCard>
        ))}

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}
