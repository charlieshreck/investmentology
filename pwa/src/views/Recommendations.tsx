import { useState } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { MarketStatus } from "../components/shared/MarketStatus";
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

function AddToPortfolioModal({
  rec,
  onClose,
  onSubmit,
}: {
  rec: Recommendation;
  onClose: () => void;
  onSubmit: (data: { ticker: string; entry_price: number; shares: number; position_type: string; thesis: string }) => void;
}) {
  const [entryPrice, setEntryPrice] = useState(rec.currentPrice.toString());
  const [shares, setShares] = useState("100");
  const [posType, setPosType] = useState("core");
  const [thesis, setThesis] = useState(rec.reasoning?.slice(0, 200) || "");

  const price = parseFloat(entryPrice) || 0;
  const qty = parseFloat(shares) || 0;
  const totalCost = price * qty;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center",
        padding: "var(--space-lg)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-surface-1)", borderRadius: "var(--radius-lg)",
          padding: "var(--space-xl)", width: "100%", maxWidth: 400,
          display: "flex", flexDirection: "column", gap: "var(--space-md)",
        }}
      >
        <div style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>
          Add {rec.ticker} to Portfolio
        </div>

        {/* Price + Shares side by side */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
          <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
            Price per share
            <input
              type="number"
              step="0.01"
              value={entryPrice}
              onChange={(e) => setEntryPrice(e.target.value)}
              style={{
                width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
                background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
                borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
                fontFamily: "var(--font-mono)",
              }}
            />
          </label>
          <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
            Shares
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              style={{
                width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
                background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
                borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
                fontFamily: "var(--font-mono)",
              }}
            />
          </label>
        </div>

        {/* Cost summary */}
        {price > 0 && qty > 0 && (
          <div style={{
            padding: "var(--space-md)",
            background: "var(--color-surface-0)",
            borderRadius: "var(--radius-sm)",
            display: "flex", flexDirection: "column", gap: "var(--space-xs)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
              <span>{qty} shares @ {formatPrice(price)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>Total cost</span>
              <span style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                {totalCost.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })}
              </span>
            </div>
          </div>
        )}

        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
          Position Type
          <select
            value={posType}
            onChange={(e) => setPosType(e.target.value)}
            style={{
              width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
            }}
          >
            <option value="core">Core</option>
            <option value="tactical">Tactical</option>
            <option value="permanent">Permanent</option>
          </select>
        </label>

        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
          Thesis
          <textarea
            value={thesis}
            onChange={(e) => setThesis(e.target.value)}
            rows={2}
            style={{
              width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
              fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", resize: "vertical",
            }}
          />
        </label>

        <div style={{ display: "flex", gap: "var(--space-md)", marginTop: "var(--space-sm)" }}>
          <button
            onClick={onClose}
            style={{
              flex: 1, padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)", color: "var(--color-text-secondary)", cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => {
              if (price > 0 && qty > 0) {
                onSubmit({
                  ticker: rec.ticker,
                  entry_price: price,
                  shares: qty,
                  position_type: posType,
                  thesis,
                });
              }
            }}
            style={{
              flex: 1, padding: "var(--space-sm) var(--space-md)",
              background: price > 0 && qty > 0 ? "var(--gradient-active)" : "var(--color-surface-2)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: price > 0 && qty > 0 ? "#fff" : "var(--color-text-muted)",
              cursor: price > 0 && qty > 0 ? "pointer" : "default",
              fontWeight: 600,
            }}
          >
            Add Position
          </button>
        </div>
      </div>
    </div>
  );
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

  const handleAddToPortfolio = async (data: {
    ticker: string; entry_price: number; shares: number; position_type: string; thesis: string;
  }) => {
    try {
      const res = await fetch("/api/invest/portfolio/positions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setAddStatus(`Added ${data.ticker} (${data.shares} shares)`);
      setPortfolioTarget(null);
      setTimeout(() => setAddStatus(null), 3000);
    } catch (err) {
      setAddStatus(`Error: ${err instanceof Error ? err.message : "failed"}`);
      setTimeout(() => setAddStatus(null), 3000);
    }
  };

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
          rec={portfolioTarget}
          onClose={() => setPortfolioTarget(null)}
          onSubmit={handleAddToPortfolio}
        />
      )}
    </div>
  );
}
