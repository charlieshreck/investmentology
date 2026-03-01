import { useEffect, useRef } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { PositionRowSkeleton } from "../components/shared/SkeletonCard";
import { MarketStatus } from "../components/shared/MarketStatus";
import { useWatchlist } from "../hooks/useWatchlist";
import { useAnalysis } from "../contexts/AnalysisContext";
import { useStore } from "../stores/useStore";

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

function pnlColor(n: number): string {
  if (n > 0) return "var(--color-success)";
  if (n < 0) return "var(--color-error)";
  return "var(--color-text-secondary)";
}

function sentimentBar(s: number): { width: string; color: string } {
  const pct = Math.abs(s) * 100;
  const color = s >= 0 ? "var(--color-success)" : "var(--color-error)";
  return { width: `${Math.max(pct, 8)}%`, color };
}

function relativeDate(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
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

/** SVG sparkline from price history data points. */
function Sparkline({ data, changePct }: { data: { date: string; price: number }[]; changePct: number }) {
  if (!data || data.length < 2) return null;
  const prices = data.map((d) => d.price).filter((p) => p > 0);
  if (prices.length < 2) return null;

  const w = 100;
  const h = 28;
  const pad = 1;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;

  const points = prices.map((p, i) => {
    const x = pad + (i / (prices.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (p - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const color = changePct >= 0 ? "var(--color-success)" : "var(--color-error)";

  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
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
  const changePct = item.changePct ?? 0;

  return (
    <div
      onClick={onClick}
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto auto auto",
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
          {item.addedAt && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {relativeDate(item.addedAt)}
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

      {/* Sparkline */}
      <div style={{ flexShrink: 0 }}>
        <Sparkline data={item.priceHistory || []} changePct={changePct} />
      </div>

      {/* Price column: entry → current + change % */}
      <div style={{ textAlign: "right", minWidth: 70 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 600 }}>
          {formatPrice(item.currentPrice)}
        </div>
        {item.priceAtAdd > 0 && (
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            from {formatPrice(item.priceAtAdd)}
          </div>
        )}
        {item.priceAtAdd > 0 && (
          <div style={{
            fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", fontWeight: 600,
            color: pnlColor(changePct),
          }}>
            {changePct >= 0 ? "+" : ""}{changePct.toFixed(1)}%
          </div>
        )}
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
  const { startAnalysis, isRunning: analysisRunning } = useAnalysis();
  const analysisProgress = useStore((s) => s.analysisProgress);
  const analyzingTicker = analysisRunning ? analysisProgress?.ticker : null;

  // Refetch when a batch analysis completes
  const wasRunning = useRef(false);
  useEffect(() => {
    if (analysisRunning) {
      wasRunning.current = true;
    } else if (wasRunning.current) {
      wasRunning.current = false;
      refetch();
    }
  }, [analysisRunning, refetch]);

  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader />
        <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: 0 }}>
          <PositionRowSkeleton />
          <PositionRowSkeleton />
          <PositionRowSkeleton />
          <PositionRowSkeleton />
          <PositionRowSkeleton />
          <PositionRowSkeleton />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader />
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
  const allTickers = sectors.flatMap((k) => groupedByState[k].map((item) => item.ticker));

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        subtitle={`${totalItems} stock${totalItems !== 1 ? "s" : ""} tagged by agents`}
        right={
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
            {allTickers.length > 0 && (
              <button
                onClick={() => { if (!analysisRunning) startAnalysis(allTickers); }}
                disabled={analysisRunning}
                style={{
                  padding: "var(--space-xs) var(--space-md)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  background: analysisRunning ? "var(--color-surface-2)" : "var(--gradient-active)",
                  color: analysisRunning ? "var(--color-text-muted)" : "#fff",
                  border: "none",
                  borderRadius: "var(--radius-full)",
                  cursor: analysisRunning ? "not-allowed" : "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                {analysisRunning ? "Running..." : `Analyze All (${allTickers.length})`}
              </button>
            )}
            <MarketStatus />
          </div>
        }
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
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            gap: "var(--space-lg)", padding: "var(--space-2xl) var(--space-xl)",
            textAlign: "center",
          }}>
            <div style={{
              width: 64, height: 64, borderRadius: "50%",
              background: "var(--color-surface-1)", border: "1px solid var(--glass-border)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </div>
            <div>
              <p style={{ margin: 0, fontSize: "var(--text-base)", fontWeight: 600, color: "var(--color-text-secondary)" }}>
                Nothing on watch yet
              </p>
              <p style={{ margin: "var(--space-sm) 0 0", fontSize: "var(--text-xs)", color: "var(--color-text-muted)", lineHeight: 1.5 }}>
                Stocks tagged WATCHLIST by the agents during analysis will appear here for tracking.
              </p>
            </div>
          </div>
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
                  onAnalyze={() => { if (!analysisRunning) startAnalysis([item.ticker]); }}
                  isAnalyzing={analyzingTicker === item.ticker}
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
