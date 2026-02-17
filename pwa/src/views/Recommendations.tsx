import { useState } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { MarketStatus } from "../components/shared/MarketStatus";
import { AddToPortfolioModal } from "../components/shared/AddToPortfolioModal";
import { useRecommendations } from "../hooks/useRecommendations";
import { verdictColor, verdictLabel, verdictBadgeVariant } from "../utils/verdictHelpers";
import type { Recommendation, AgentStance } from "../types/models";
import { useStore } from "../stores/useStore";

function formatCap(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function formatPrice(n: number): string {
  return n > 0 ? `$${n.toFixed(2)}` : "—";
}

function sentimentBar(s: number): { width: string; color: string } {
  const pct = Math.abs(s) * 100;
  const color = s >= 0 ? "var(--color-success)" : "var(--color-error)";
  return { width: `${Math.max(pct, 8)}%`, color };
}

function RecCard({
  rec,
  onOpen,
  onAddToPortfolio,
}: {
  rec: Recommendation;
  onOpen: () => void;
  onAddToPortfolio: () => void;
}) {
  const stances = (rec.agentStances || []) as AgentStance[];

  return (
    <div
      onClick={onOpen}
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto auto auto",
        gap: "var(--space-md)",
        alignItems: "center",
        padding: "var(--space-md) var(--space-lg)",
        borderRadius: "var(--radius-sm)",
        background: "var(--color-surface-0)",
        cursor: "pointer",
        transition: "background var(--duration-fast) var(--ease-out)",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-1)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-0)"; }}
    >
      {/* Col 1: Ticker + info */}
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
          <span style={{ fontWeight: 700, fontFamily: "var(--font-mono)", fontSize: "var(--text-base)" }}>
            {rec.ticker}
          </span>
          {rec.confidence != null && (
            <span style={{ fontSize: "var(--text-xs)", color: verdictColor[rec.verdict] || "var(--color-text-muted)" }}>
              {(rec.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>
        <div style={{
          fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {rec.name} {rec.sector ? `/ ${rec.sector}` : ""}
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
        {/* Risk flags */}
        {rec.riskFlags && rec.riskFlags.length > 0 && (
          <div style={{ fontSize: 9, color: "var(--color-warning)", marginTop: 2 }}>
            {rec.riskFlags.length} risk flag{rec.riskFlags.length > 1 ? "s" : ""}
          </div>
        )}
      </div>

      {/* Col 2: Consensus */}
      <div style={{ textAlign: "right" }}>
        {rec.consensusScore != null && (
          <div style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)" }}>
            {rec.consensusScore > 0 ? "+" : ""}{rec.consensusScore.toFixed(2)}
          </div>
        )}
        {rec.marketCap > 0 && (
          <div style={{ fontSize: 9, color: "var(--color-text-muted)" }}>{formatCap(rec.marketCap)}</div>
        )}
      </div>

      {/* Col 3: Price */}
      <div style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>
        {formatPrice(rec.currentPrice)}
      </div>

      {/* Col 4: Add button */}
      <button
        onClick={(e) => { e.stopPropagation(); onAddToPortfolio(); }}
        style={{
          padding: "var(--space-xs) var(--space-md)",
          borderRadius: "var(--radius-sm)",
          background: "var(--color-surface-2)",
          border: "1px solid var(--glass-border)",
          color: "var(--color-accent-bright)",
          cursor: "pointer",
          fontSize: "var(--text-xs)",
          fontWeight: 500,
          whiteSpace: "nowrap",
        }}
      >
        + Portfolio
      </button>
    </div>
  );
}

export function Recommendations() {
  const { groupedByVerdict, totalCount, loading, error, refetch } = useRecommendations();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const [portfolioTarget, setPortfolioTarget] = useState<Recommendation | null>(null);
  const [addStatus, setAddStatus] = useState<string | null>(null);

  if (loading) {
    return (
      <div style={{ padding: "var(--space-xl)", paddingTop: "calc(var(--header-height) + var(--space-xl))" }}>
        <ViewHeader title="Recommendations" />
        <p style={{ color: "var(--color-text-muted)" }}>Loading recommendations...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "var(--space-xl)", paddingTop: "calc(var(--header-height) + var(--space-xl))" }}>
        <ViewHeader title="Recommendations" />
        <BentoCard>
          <p style={{ color: "var(--color-error)" }}>Failed to load: {error}</p>
        </BentoCard>
      </div>
    );
  }

  const verdictOrder = Object.keys(groupedByVerdict);

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Recommendations"
        subtitle={`${totalCount} actionable signal${totalCount !== 1 ? "s" : ""}`}
        right={<MarketStatus />}
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Status toast */}
        {addStatus && (
          <div style={{
            padding: "var(--space-sm) var(--space-lg)",
            borderRadius: "var(--radius-sm)",
            background: addStatus.startsWith("Error") ? "var(--color-error)" : "var(--color-success)",
            color: "#fff", fontSize: "var(--text-sm)", fontWeight: 500,
          }}>
            {addStatus}
          </div>
        )}

        {/* Verdict group badges */}
        <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
          {verdictOrder.map((v) => (
            <a
              key={v}
              href={`#verdict-${v}`}
              style={{ textDecoration: "none" }}
            >
              <Badge variant={verdictBadgeVariant[v] || "neutral"}>
                {verdictLabel[v] || v} ({groupedByVerdict[v].length})
              </Badge>
            </a>
          ))}
          <button
            onClick={() => refetch()}
            style={{
              padding: "var(--space-xs) var(--space-md)",
              borderRadius: "var(--radius-full)",
              background: "var(--color-surface-2)",
              border: "1px solid var(--glass-border)",
              color: "var(--color-text-secondary)",
              cursor: "pointer",
              fontSize: "var(--text-xs)",
            }}
          >
            Refresh
          </button>
        </div>

        {/* Empty state */}
        {totalCount === 0 && (
          <BentoCard>
            <div style={{ textAlign: "center", padding: "var(--space-xl)", color: "var(--color-text-muted)" }}>
              No recommendations yet. Run analysis on stocks from the Screener or Watchlist.
            </div>
          </BentoCard>
        )}

        {/* Verdict groups */}
        {verdictOrder.map((v) => {
          const recs = groupedByVerdict[v];
          return (
            <div key={v} id={`verdict-${v}`}>
              <BentoCard title={verdictLabel[v] || v}>
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-sm)",
                  marginBottom: "var(--space-md)",
                }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: verdictColor[v] || "var(--color-text-muted)",
                  }} />
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                    {recs.length} stock{recs.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                  {recs.map((rec) => (
                    <RecCard
                      key={rec.ticker}
                      rec={rec}
                      onOpen={() => setOverlayTicker(rec.ticker)}
                      onAddToPortfolio={() => setPortfolioTarget(rec)}
                    />
                  ))}
                </div>
              </BentoCard>
            </div>
          );
        })}

        <div style={{ height: "var(--nav-height)" }} />
      </div>

      {/* Add to Portfolio Modal */}
      {portfolioTarget && (
        <AddToPortfolioModal
          ticker={portfolioTarget.ticker}
          currentPrice={portfolioTarget.currentPrice}
          defaultThesis={portfolioTarget.reasoning || ""}
          onClose={() => setPortfolioTarget(null)}
          onSuccess={(msg) => { setAddStatus(msg); setTimeout(() => setAddStatus(null), 3000); }}
          onError={(msg) => { setAddStatus(msg); setTimeout(() => setAddStatus(null), 3000); }}
        />
      )}
    </div>
  );
}
