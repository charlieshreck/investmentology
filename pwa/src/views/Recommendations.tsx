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
  if (n >= 1e12) return `£${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `£${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `£${(n / 1e6).toFixed(0)}M`;
  return `£${n.toLocaleString()}`;
}

function formatPrice(n: number): string {
  return n > 0 ? `£${n.toFixed(2)}` : "\u2014";
}

function buzzPill(buzzLabel?: string) {
  if (!buzzLabel) return null;
  const colors: Record<string, { bg: string; fg: string }> = {
    HIGH: { bg: "rgba(248, 113, 113, 0.15)", fg: "var(--color-error)" },
    ELEVATED: { bg: "rgba(251, 191, 36, 0.15)", fg: "var(--color-warning)" },
    NORMAL: { bg: "rgba(148, 163, 184, 0.12)", fg: "var(--color-text-muted)" },
    QUIET: { bg: "rgba(52, 211, 153, 0.12)", fg: "var(--color-success)" },
  };
  const c = colors[buzzLabel] || colors.NORMAL;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 3,
      padding: "1px 6px", borderRadius: 99, fontSize: 9, fontWeight: 600,
      background: c.bg, color: c.fg, letterSpacing: "0.03em",
    }}>
      {buzzLabel === "HIGH" ? "🔥" : buzzLabel === "QUIET" ? "🤫" : ""} {buzzLabel}
    </span>
  );
}

function tierPill(tier?: string | null) {
  if (!tier) return null;
  const colors: Record<string, { bg: string; fg: string }> = {
    HIGH_CONVICTION: { bg: "rgba(52, 211, 153, 0.15)", fg: "var(--color-success)" },
    MIXED: { bg: "rgba(251, 191, 36, 0.15)", fg: "var(--color-warning)" },
    CONTRARIAN: { bg: "rgba(168, 85, 247, 0.15)", fg: "#a855f7" },
  };
  const labels: Record<string, string> = {
    HIGH_CONVICTION: "High Conv.",
    MIXED: "Mixed",
    CONTRARIAN: "Contrarian",
  };
  const c = colors[tier] || colors.MIXED;
  return (
    <span style={{
      display: "inline-flex", padding: "1px 6px", borderRadius: 99,
      fontSize: 9, fontWeight: 600, background: c.bg, color: c.fg,
    }}>
      {labels[tier] || tier}
    </span>
  );
}

function stabilityPill(label?: string) {
  if (!label || label === "UNKNOWN") return null;
  const colors: Record<string, { bg: string; fg: string }> = {
    STABLE: { bg: "rgba(52, 211, 153, 0.12)", fg: "var(--color-success)" },
    MODERATE: { bg: "rgba(251, 191, 36, 0.12)", fg: "var(--color-warning)" },
    UNSTABLE: { bg: "rgba(248, 113, 113, 0.12)", fg: "var(--color-error)" },
  };
  const c = colors[label] || colors.MODERATE;
  return (
    <span style={{
      display: "inline-flex", padding: "1px 6px", borderRadius: 99,
      fontSize: 9, fontWeight: 600, background: c.bg, color: c.fg,
    }}>
      {label}
    </span>
  );
}

function earningsPill(momentum?: { label: string; beatStreak: number }) {
  if (!momentum || momentum.label === "STABLE") return null;
  const isPositive = momentum.label === "STRONG_UPWARD" || momentum.label === "IMPROVING";
  const fg = isPositive ? "var(--color-success)" : "var(--color-error)";
  const bg = isPositive ? "rgba(52, 211, 153, 0.12)" : "rgba(248, 113, 113, 0.12)";
  const arrow = isPositive ? "↑" : "↓";
  const short: Record<string, string> = {
    STRONG_UPWARD: "EPS ↑↑",
    IMPROVING: "EPS ↑",
    WEAKENING: "EPS ↓",
    DECLINING: "EPS ↓↓",
  };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 2,
      padding: "1px 6px", borderRadius: 99,
      fontSize: 9, fontWeight: 600, background: bg, color: fg,
    }}>
      {short[momentum.label] || `${arrow} EPS`}
      {momentum.beatStreak >= 3 && (
        <span style={{ fontSize: 8, opacity: 0.8 }}>({momentum.beatStreak}x beat)</span>
      )}
    </span>
  );
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
  const size = 44;
  const stroke = 3.5;
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
        fontSize: 11, fontWeight: 700, fontFamily: "var(--font-mono)", color,
      }}>
        {pct}%
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
        gridTemplateColumns: "auto 1fr auto auto auto",
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
      {/* Success probability ring */}
      {successRing(rec.successProbability)}

      {/* Ticker + info */}
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
          <span style={{ fontWeight: 700, fontFamily: "var(--font-mono)", fontSize: "var(--text-base)" }}>
            {rec.ticker}
          </span>
          {rec.confidence != null && (
            <span style={{ fontSize: "var(--text-xs)", color: verdictColor[rec.verdict] || "var(--color-text-muted)" }}>
              {(rec.confidence * 100).toFixed(0)}% conf
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
        {/* Signal pills */}
        <div style={{ display: "flex", gap: 3, marginTop: 3, flexWrap: "wrap", alignItems: "center" }}>
          {rec.riskFlags && rec.riskFlags.length > 0 && (
            <span style={{
              display: "inline-flex", padding: "1px 5px", borderRadius: 99,
              fontSize: 9, fontWeight: 600,
              background: "rgba(251, 191, 36, 0.12)", color: "var(--color-warning)",
            }}>
              {rec.riskFlags.length} risk
            </span>
          )}
          {tierPill(rec.consensusTier)}
          {stabilityPill(rec.stabilityLabel)}
          {buzzPill(rec.buzzLabel)}
          {earningsPill(rec.earningsMomentum)}
          {rec.contrarianFlag && (
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 2,
              padding: "1px 6px", borderRadius: 99,
              fontSize: 9, fontWeight: 700,
              background: "rgba(168, 85, 247, 0.15)", color: "#a855f7",
            }}>
              ◆ Contrarian
            </span>
          )}
          {rec.dividendYield != null && rec.dividendYield > 0 && (
            <span style={{
              display: "inline-flex", padding: "1px 5px", borderRadius: 99,
              fontSize: 9, fontWeight: 600,
              background: "rgba(52, 211, 153, 0.08)", color: "var(--color-text-muted)",
            }}>
              {rec.dividendYield.toFixed(1)}% div
            </span>
          )}
        </div>
      </div>

      {/* Consensus */}
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

      {/* Price */}
      <div style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>
        {formatPrice(rec.currentPrice)}
      </div>

      {/* Add button */}
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
        <ViewHeader title="Recommend" />
        <p style={{ color: "var(--color-text-muted)" }}>Loading recommendations...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "var(--space-xl)", paddingTop: "calc(var(--header-height) + var(--space-xl))" }}>
        <ViewHeader title="Recommend" />
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
        title="Recommend"
        subtitle={`${totalCount} stock${totalCount !== 1 ? "s" : ""} ready for portfolio action`}
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
              No recommendations yet. Stocks need Strong Buy, Buy, or Accumulate verdicts to appear here.
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
