import { useCallback } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { useWatchlist } from "../hooks/useWatchlist";
import { useAnalyze } from "../hooks/useAnalyze";
import { useStore } from "../stores/useStore";
import { verdictColor } from "../utils/verdictHelpers";
import type { WatchlistItem, AgentStance } from "../types/models";

function formatCap(cap: number): string {
  if (!cap) return "";
  if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`;
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`;
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(0)}M`;
  return `$${cap.toLocaleString()}`;
}

function formatPrice(n: number): string {
  return n > 0 ? `$${n.toFixed(2)}` : "\u2014";
}

function sentimentBar(s: number): { width: string; color: string } {
  const pct = Math.abs(s) * 100;
  const color = s >= 0 ? "var(--color-success)" : "var(--color-error)";
  return { width: `${Math.max(pct, 8)}%`, color };
}

function successRing(probability: number | null) {
  if (probability == null) return null;
  const pct = Math.round(probability * 100);
  const color =
    pct >= 70 ? "var(--color-success)" : pct >= 40 ? "var(--color-warning)" : "var(--color-error)";
  const size = 40;
  const stroke = 3;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - probability);

  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--color-surface-2)" strokeWidth={stroke}
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={circumference} strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          strokeLinecap="round"
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)", color,
      }}>
        {pct}%
      </div>
    </div>
  );
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
  const v = item.verdict;
  const stances = (v?.agentStances || []) as AgentStance[];
  const riskFlags = v?.riskFlags as string[] | null | undefined;
  const confPct = v?.confidence != null ? `${(v.confidence * 100).toFixed(0)}% conf` : null;

  return (
    <div
      onClick={onClick}
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto auto",
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
      {/* Success probability ring */}
      {successRing(item.successProbability)}

      {/* Ticker / name / agent stances */}
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
          <span style={{ fontWeight: 700, fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>
            {item.ticker}
          </span>
          {confPct && (
            <span style={{ fontSize: "var(--text-xs)", color: verdictColor["WATCHLIST"] || "var(--color-text-muted)" }}>
              {confPct}
            </span>
          )}
        </div>
        <div style={{
          fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {item.name}
          {item.marketCap > 0 && ` · ${formatCap(item.marketCap)}`}
        </div>
        {/* Agent stances */}
        {stances.length > 0 && (
          <div style={{ display: "flex", gap: "var(--space-xs)", marginTop: "var(--space-xs)" }}>
            {stances.map((a) => {
              const bar = sentimentBar(a.sentiment);
              return (
                <div key={a.name} style={{ display: "flex", alignItems: "center", gap: 3 }}>
                  <span style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "capitalize" }}>
                    {a.name.slice(0, 3)}
                  </span>
                  <div style={{
                    width: 32, height: 4, borderRadius: 2,
                    background: "var(--color-surface-2)", overflow: "hidden",
                  }}>
                    <div style={{ height: "100%", width: bar.width, background: bar.color, borderRadius: 2 }} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {riskFlags && riskFlags.length > 0 && (
          <div style={{ fontSize: 9, color: "var(--color-warning)", marginTop: 2 }}>
            {riskFlags.length} risk flag{riskFlags.length > 1 ? "s" : ""}
          </div>
        )}
      </div>

      {/* Price */}
      <div style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>
        {formatPrice(item.currentPrice)}
      </div>

      {/* Re-analyze button */}
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
        {isAnalyzing ? "..." : "Re-analyze"}
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
        <ViewHeader title="Watch" />
        <div style={{ padding: "var(--space-xl)" }}>
          <p style={{ color: "var(--color-text-muted)" }}>Loading...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Watch" />
        <div style={{ padding: "var(--space-xl)" }}>
          <BentoCard>
            <p style={{ color: "var(--color-error)" }}>Failed to load: {error}</p>
          </BentoCard>
        </div>
      </div>
    );
  }

  const sectors = Object.keys(groupedByState);
  const totalItems = sectors.reduce((s, k) => s + groupedByState[k].length, 0);

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Watch"
        subtitle={`${totalItems} stock${totalItems !== 1 ? "s" : ""} tagged by agents · stepping stone to Recommend`}
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Sector badges */}
        {sectors.length > 1 && (
          <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
            {sectors.map((sector) => (
              <Badge key={sector} variant="neutral">
                {sector} ({groupedByState[sector].length})
              </Badge>
            ))}
          </div>
        )}

        {/* Empty state */}
        {totalItems === 0 && (
          <BentoCard>
            <div style={{ textAlign: "center", padding: "var(--space-xl)", color: "var(--color-text-muted)" }}>
              No stocks on watch yet. Run analysis on Screen stocks — those tagged WATCHLIST by agents appear here.
            </div>
          </BentoCard>
        )}

        {/* Grouped by sector */}
        {sectors.map((sector) => (
          <BentoCard key={sector} title={sector}>
            <div style={{ display: "flex", flexDirection: "column" }}>
              {groupedByState[sector].map((item) => (
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
