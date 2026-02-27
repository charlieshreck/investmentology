import { useState, useEffect, useRef } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { BalanceBar, RiskSpectrum } from "../components/shared/BalanceBar";
import { MarketStatus } from "../components/shared/MarketStatus";
import { CorrelationHeatmap } from "../components/charts/CorrelationHeatmap";
import { usePortfolio } from "../hooks/usePortfolio";
import { useCorrelations } from "../hooks/useCorrelations";
import { useConfetti } from "../hooks/useConfetti";
import { useWebSocket } from "../hooks/useWebSocket";
import type { Position, Alert } from "../types/models";
import { useStore } from "../stores/useStore";

function formatCurrency(n: number): string {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function formatPct(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function pnlColor(n: number): string {
  if (n > 0) return "var(--color-success)";
  if (n < 0) return "var(--color-error)";
  return "var(--color-text-secondary)";
}

function alertVariant(severity: Alert["severity"]): "accent" | "success" | "warning" | "error" | "neutral" {
  const map: Record<string, "accent" | "success" | "warning" | "error" | "neutral"> = {
    info: "accent",
    warning: "warning",
    error: "error",
    critical: "error",
  };
  return map[severity] ?? "neutral";
}

interface BalanceData {
  sectors: Array<{ name: string; pct: number; zone: string; color: string; softMax: number; warnMax: number; tickers: string[] }>;
  riskCategories: Array<{ name: string; pct: number; zone: string; idealMin: number; idealMax: number; warnMax: number }>;
  positionCount: number;
  sectorCount: number;
  health: string;
  insights: string[];
}

function usePortfolioBalance(positionCount: number) {
  const [balance, setBalance] = useState<BalanceData | null>(null);

  useEffect(() => {
    if (positionCount === 0) { setBalance(null); return; }
    fetch("/api/invest/portfolio/balance")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => setBalance(data))
      .catch(() => setBalance(null));
  }, [positionCount]);

  return balance;
}

function ClosePositionModal({
  position,
  onClose,
  onSubmit,
}: {
  position: Position;
  onClose: () => void;
  onSubmit: (positionId: number, exitPrice: number) => void;
}) {
  const [exitPrice, setExitPrice] = useState((position.currentPrice ?? position.avgCost).toString());

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
          padding: "var(--space-xl)", width: "100%", maxWidth: 360,
          display: "flex", flexDirection: "column", gap: "var(--space-md)",
        }}
      >
        <div style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>
          Close {position.ticker}
        </div>
        <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
          {position.shares} shares @ avg {formatCurrency(position.avgCost)}
        </div>
        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
          Exit Price
          <input
            type="number"
            step="0.01"
            value={exitPrice}
            onChange={(e) => setExitPrice(e.target.value)}
            style={{
              width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
              fontFamily: "var(--font-mono)",
            }}
          />
        </label>
        {(() => {
          const ep = parseFloat(exitPrice);
          if (!isNaN(ep) && ep > 0) {
            const pnl = (ep - position.avgCost) * position.shares;
            const pnlPct = ((ep - position.avgCost) / position.avgCost) * 100;
            return (
              <div style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", color: pnlColor(pnl) }}>
                Realized P&L: {formatCurrency(pnl)} ({formatPct(pnlPct)})
              </div>
            );
          }
          return null;
        })()}
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
              const ep = parseFloat(exitPrice);
              if (ep > 0 && position.id != null) {
                onSubmit(position.id, ep);
              }
            }}
            style={{
              flex: 1, padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-error)", border: "none",
              borderRadius: "var(--radius-sm)", color: "#fff", cursor: "pointer", fontWeight: 600,
            }}
          >
            Close Position
          </button>
        </div>
      </div>
    </div>
  );
}

interface AdvisorCard {
  type: string;
  ticker: string;
  title: string;
  detail: string;
  reasoning: string;
  priority: string;
}

interface BriefingSummary {
  date: string;
  pendulumLabel: string;
  pendulumScore: number;
  positionCount: number;
  totalValue: number;
  totalUnrealizedPnl: number;
  newRecommendationCount: number;
  alertCount: number;
  overallRiskLevel: string;
  topActions: Array<{ category: string; ticker: string; action: string }>;
}

export function Portfolio() {
  const {
    positions, totalValue, dayPnl, dayPnlPct, cash, alerts,
    closedPositions, totalRealizedPnl,
    loading, error, closePosition,
  } = usePortfolio();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const performance = useStore((s) => s.performance);
  const [closeTarget, setCloseTarget] = useState<Position | null>(null);
  const [closeStatus, setCloseStatus] = useState<string | null>(null);
  const [advisorCards, setAdvisorCards] = useState<AdvisorCard[]>([]);
  const [briefing, setBriefing] = useState<BriefingSummary | null>(null);
  const balance = usePortfolioBalance(positions.length);

  // Fetch advisor cards
  useEffect(() => {
    if (positions.length === 0) return;
    fetch("/api/invest/portfolio/advisor")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data?.actions) setAdvisorCards(data.actions); })
      .catch(() => {});
  }, [positions.length]);

  // Fetch daily briefing summary
  useEffect(() => {
    if (positions.length === 0) return;
    fetch("/api/invest/daily/briefing/summary")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data?.date) setBriefing(data); })
      .catch(() => {});
  }, [positions.length]);
  const tickerFingerprint = positions.map((p) => p.ticker).sort().join(",");
  const { data: corrData } = useCorrelations(positions.length, tickerFingerprint);
  const { fire } = useConfetti();
  const { status: wsStatus, prices: livePrices } = useWebSocket({ enabled: positions.length > 0 });
  const prevPnlSign = useRef<number | null>(null);

  // Celebrate when portfolio PnL transitions from negative/zero to positive (not on initial load)
  const totalPnlForConfetti = positions.reduce((s, p) => s + p.unrealizedPnl, 0);
  useEffect(() => {
    if (!loading && positions.length > 0) {
      const sign = totalPnlForConfetti > 0 ? 1 : totalPnlForConfetti < 0 ? -1 : 0;
      if (prevPnlSign.current !== null && prevPnlSign.current <= 0 && sign > 0) {
        fire("profit", "portfolio-positive");
      }
      prevPnlSign.current = sign;
    }
  }, [totalPnlForConfetti, loading, positions.length, fire]);

  const handleClose = async (positionId: number, exitPrice: number) => {
    try {
      await closePosition(positionId, exitPrice);
      setCloseStatus("Position closed");
      setCloseTarget(null);
      setTimeout(() => setCloseStatus(null), 3000);
    } catch (err) {
      setCloseStatus(`Error: ${err instanceof Error ? err.message : "failed"}`);
      setTimeout(() => setCloseStatus(null), 3000);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "var(--space-xl)", paddingTop: "calc(var(--header-height) + var(--space-xl))" }}>
        <ViewHeader title="Portfolio" />
        <p style={{ color: "var(--color-text-muted)" }}>Loading portfolio...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "var(--space-xl)", paddingTop: "calc(var(--header-height) + var(--space-xl))" }}>
        <ViewHeader title="Portfolio" />
        <BentoCard>
          <p style={{ color: "var(--color-error)" }}>Failed to load portfolio: {error}</p>
        </BentoCard>
      </div>
    );
  }

  // Merge live WebSocket prices into positions
  const enrichedPositions = positions.map((p) => {
    const live = livePrices[p.ticker];
    if (!live) return p;
    const livePrice = live.price;
    const mv = livePrice * p.shares;
    const cost = p.avgCost * p.shares;
    const pnl = mv - cost;
    const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
    return {
      ...p,
      currentPrice: livePrice,
      marketValue: mv,
      unrealizedPnl: pnl,
      unrealizedPnlPct: pnlPct,
      dayChange: live.change * p.shares,
      dayChangePct: live.changePct,
    };
  });

  const totalPnl = enrichedPositions.reduce((s, p) => s + p.unrealizedPnl, 0);
  const enrichedTotalValue = enrichedPositions.reduce((s, p) => s + p.marketValue, 0) + cash;
  const totalPnlPct = enrichedTotalValue > 0 ? (totalPnl / (enrichedTotalValue - totalPnl - cash)) * 100 : 0;
  const cashPct = enrichedTotalValue > 0 ? (cash / enrichedTotalValue) * 100 : 0;

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader title="Portfolio" subtitle={`${positions.length} positions`} right={<MarketStatus wsStatus={wsStatus} />} />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Metrics row */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
          <BentoCard title="Total Value">
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
              {formatCurrency(enrichedTotalValue || totalValue)}
            </div>
          </BentoCard>
          <BentoCard title="Day P&L">
            {(() => {
              const enrichedDayPnl = enrichedPositions.reduce((s, p) => s + (p.dayChange || 0), 0);
              const liveDayPnl = Object.keys(livePrices).length > 0 ? enrichedDayPnl : dayPnl;
              const liveDayPnlPct = Object.keys(livePrices).length > 0 && enrichedTotalValue > 0
                ? (enrichedDayPnl / (enrichedTotalValue - enrichedDayPnl)) * 100
                : dayPnlPct;
              return (
                <>
                  <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-mono)", color: pnlColor(liveDayPnl) }}>
                    {formatCurrency(liveDayPnl)}
                  </div>
                  <div style={{ fontSize: "var(--text-sm)", color: pnlColor(liveDayPnlPct) }}>
                    {formatPct(liveDayPnlPct)}
                  </div>
                </>
              );
            })()}
          </BentoCard>
          <BentoCard title="Total P&L">
            <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, fontFamily: "var(--font-mono)", color: pnlColor(totalPnl) }}>
              {formatCurrency(totalPnl)}
            </div>
            <div style={{ fontSize: "var(--text-sm)", color: pnlColor(totalPnlPct) }}>
              {formatPct(totalPnlPct)}
            </div>
          </BentoCard>
          <BentoCard title="Cash">
            <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, fontFamily: "var(--font-mono)" }}>
              {formatCurrency(cash)}
            </div>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
              {cashPct.toFixed(1)}% of portfolio
            </div>
          </BentoCard>
        </div>

        {/* Performance Metrics */}
        {performance && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr", gap: "var(--space-md)" }}>
            <BentoCard title="Alpha vs SPY">
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, fontFamily: "var(--font-mono)", color: performance.alphaPct != null ? pnlColor(performance.alphaPct) : undefined }}>
                {performance.alphaPct != null ? `${performance.alphaPct >= 0 ? "+" : ""}${performance.alphaPct.toFixed(1)}%` : "—"}
              </div>
            </BentoCard>
            <BentoCard title="Sharpe">
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                {performance.sharpeRatio != null ? performance.sharpeRatio.toFixed(2) : "—"}
              </div>
            </BentoCard>
            <BentoCard title="Sortino">
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                {performance.sortinoRatio != null ? performance.sortinoRatio.toFixed(2) : "—"}
              </div>
            </BentoCard>
            <BentoCard title="Win Rate">
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                {performance.winRate != null ? `${(performance.winRate * 100).toFixed(0)}%` : "—"}
              </div>
            </BentoCard>
            <BentoCard title="Max DD">
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, fontFamily: "var(--font-mono)", color: "var(--color-error)" }}>
                {performance.maxDrawdownPct != null ? `${performance.maxDrawdownPct.toFixed(1)}%` : "—"}
              </div>
            </BentoCard>
          </div>
        )}

        {/* Daily Briefing */}
        {briefing && (
          <BentoCard title="Daily Briefing">
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", marginBottom: "var(--space-sm)" }}>
              <span style={{ fontWeight: 600, fontSize: "var(--text-base)", color: "var(--color-accent-bright)" }}>
                {briefing.pendulumLabel}
              </span>
              <Badge variant={briefing.overallRiskLevel === "low" ? "success" : briefing.overallRiskLevel === "medium" ? "warning" : "error"}>
                {briefing.overallRiskLevel} risk
              </Badge>
              {briefing.alertCount > 0 && (
                <Badge variant="warning">{briefing.alertCount} alert{briefing.alertCount !== 1 ? "s" : ""}</Badge>
              )}
            </div>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
              {briefing.positionCount} positions · {formatCurrency(briefing.totalValue)} total · {formatCurrency(briefing.totalUnrealizedPnl)} unrealized P&L
              {briefing.newRecommendationCount > 0 && ` · ${briefing.newRecommendationCount} new recommendation${briefing.newRecommendationCount !== 1 ? "s" : ""}`}
            </div>
            {briefing.topActions.length > 0 && (
              <div style={{ marginTop: "var(--space-sm)", display: "flex", gap: "var(--space-xs)", flexWrap: "wrap" }}>
                {briefing.topActions.map((a, i) => (
                  <Badge key={i} variant="neutral">{a.ticker}: {a.action}</Badge>
                ))}
              </div>
            )}
          </BentoCard>
        )}

        {/* Advisor Actions */}
        {advisorCards.length > 0 && (
          <BentoCard title="Advisor Actions">
            <div style={{ display: "flex", gap: "var(--space-sm)", overflowX: "auto", paddingBottom: "var(--space-xs)" }}>
              {advisorCards.map((card, i) => {
                const actionColors: Record<string, string> = {
                  SELL: "var(--color-error)", TRIM: "var(--color-warning)", ADD_MORE: "var(--color-success)",
                  DEPLOY_CASH: "var(--color-accent)", DIVERSIFY: "var(--color-info)", REANALYZE: "var(--color-text-muted)",
                };
                const color = actionColors[card.type] || "var(--color-text-muted)";
                const text = card.reasoning || card.detail || card.title || "";
                return (
                  <div
                    key={i}
                    onClick={() => card.ticker && setOverlayTicker(card.ticker)}
                    style={{
                      flexShrink: 0, minWidth: 160, padding: "var(--space-md)",
                      background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)",
                      borderLeft: `3px solid ${color}`, cursor: card.ticker ? "pointer" : "default",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: "var(--space-xs)" }}>
                      <Badge variant={card.type === "SELL" ? "error" : card.type === "TRIM" ? "warning" : card.type === "ADD_MORE" ? "success" : "accent"}>
                        {card.type.replace(/_/g, " ")}
                      </Badge>
                      {card.ticker && <span style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{card.ticker}</span>}
                    </div>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.4 }}>
                      {text.length > 80 ? text.slice(0, 80) + "..." : text}
                    </div>
                  </div>
                );
              })}
            </div>
          </BentoCard>
        )}

        {/* Portfolio Balance */}
        {balance && balance.sectors.length > 0 && (
          <>
            <BentoCard title="Balance">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-md)" }}>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {balance.sectorCount} sector{balance.sectorCount !== 1 ? "s" : ""} across {balance.positionCount} positions
                </span>
                <Badge variant={
                  balance.health === "excellent" ? "success" :
                  balance.health === "good" ? "success" :
                  balance.health === "fair" ? "warning" : "error"
                }>
                  {balance.health}
                </Badge>
              </div>

              {/* Sector bars */}
              <div style={{ marginBottom: "var(--space-lg)" }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-sm)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Sector Allocation
                </div>
                {balance.sectors.map((s) => (
                  <BalanceBar
                    key={s.name}
                    label={s.name}
                    pct={s.pct}
                    softMax={s.softMax}
                    warnMax={s.warnMax}
                    color={s.color}
                  />
                ))}
              </div>

              {/* Risk spectrum */}
              <div style={{ marginBottom: "var(--space-lg)" }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-sm)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Risk Spectrum
                </div>
                <RiskSpectrum categories={balance.riskCategories} />
              </div>

              {/* Insights */}
              {balance.insights.length > 0 && (
                <div style={{
                  padding: "var(--space-md)",
                  background: "var(--color-surface-0)",
                  borderRadius: "var(--radius-sm)",
                  borderLeft: `3px solid ${
                    balance.health === "excellent" || balance.health === "good" ? "var(--color-success)" :
                    balance.health === "fair" ? "var(--color-warning)" : "var(--color-error)"
                  }`,
                }}>
                  {balance.insights.map((insight, i) => (
                    <div key={i} style={{
                      fontSize: "var(--text-sm)",
                      color: "var(--color-text-secondary)",
                      lineHeight: 1.5,
                      marginBottom: i < balance.insights.length - 1 ? "var(--space-sm)" : 0,
                    }}>
                      {insight}
                    </div>
                  ))}
                </div>
              )}
            </BentoCard>
          </>
        )}

        {/* Correlation Heatmap */}
        {corrData && corrData.tickers.length >= 2 && corrData.correlations.length > 0 && (
          <BentoCard title="Correlation Matrix (90d)">
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-md)" }}>
              Pairwise price correlations across holdings
            </div>
            <CorrelationHeatmap tickers={corrData.tickers} correlations={corrData.correlations} />
          </BentoCard>
        )}

        {/* Positions Table */}
        <BentoCard title="Positions">
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
              <thead>
                <tr>
                  {["Ticker", "Avg Cost", "P&L %", "Day %", "Weight", "Value", "Days", ""].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: h === "Ticker" ? "left" : "right",
                        padding: "var(--space-md)",
                        color: "var(--color-text-muted)",
                        fontWeight: 500,
                        fontSize: "var(--text-xs)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        borderBottom: "1px solid var(--glass-border)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {enrichedPositions.map((p) => (
                  <tr
                    key={p.ticker}
                    onClick={() => setOverlayTicker(p.ticker)}
                    style={{ cursor: "pointer" }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-1)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                  >
                    <td style={{ padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)", fontWeight: 600 }}>
                      {p.ticker}
                    </td>
                    <td style={{ padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                      {formatCurrency(p.avgCost)}
                    </td>
                    <td style={{ padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)", color: pnlColor(p.unrealizedPnlPct) }}>
                      {formatPct(p.unrealizedPnlPct)}
                    </td>
                    <td style={{ padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)", color: pnlColor(p.dayChangePct) }}>
                      {formatPct(p.dayChangePct)}
                    </td>
                    <td style={{ padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                      {p.weight.toFixed(1)}%
                    </td>
                    <td style={{ padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                      {formatCurrency(p.marketValue)}
                    </td>
                    <td style={{ padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
                      {p.entryDate ? Math.floor((Date.now() - new Date(p.entryDate).getTime()) / 86400000) : "—"}
                    </td>
                    <td style={{ padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right" }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); setCloseTarget(p); }}
                        style={{
                          padding: "var(--space-xs) var(--space-sm)",
                          borderRadius: "var(--radius-sm)",
                          background: "transparent",
                          border: "1px solid var(--glass-border)",
                          color: "var(--color-text-muted)",
                          cursor: "pointer",
                          fontSize: "var(--text-xs)",
                        }}
                      >
                        Close
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </BentoCard>

        {/* Alerts */}
        {alerts.length > 0 && (
          <BentoCard title="Active Alerts">
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
              {alerts.map((a) => (
                <div
                  key={a.id}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "var(--space-md)",
                    padding: "var(--space-md)",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--color-surface-0)",
                  }}
                >
                  <Badge variant={alertVariant(a.severity)}>{a.severity}</Badge>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, fontSize: "var(--text-sm)" }}>
                      {a.ticker && <span style={{ color: "var(--color-accent-bright)", marginRight: "var(--space-sm)" }}>{a.ticker}</span>}
                      {a.title}
                    </div>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-xs)" }}>
                      {a.message}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </BentoCard>
        )}

        {/* Status toast */}
        {closeStatus && (
          <div style={{
            padding: "var(--space-sm) var(--space-lg)",
            borderRadius: "var(--radius-sm)",
            background: closeStatus.startsWith("Error") ? "var(--color-error)" : "var(--color-success)",
            color: "#fff", fontSize: "var(--text-sm)", fontWeight: 500,
          }}>
            {closeStatus}
          </div>
        )}

        {/* Closed Positions */}
        {closedPositions.length > 0 && (
          <BentoCard title="Closed Positions">
            <div style={{ marginBottom: "var(--space-md)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
                {closedPositions.length} trade{closedPositions.length !== 1 ? "s" : ""}
              </span>
              <span style={{
                fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", fontWeight: 600,
                color: pnlColor(totalRealizedPnl),
              }}>
                Total: {formatCurrency(totalRealizedPnl)}
              </span>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
                <thead>
                  <tr>
                    {["Ticker", "Entry", "Exit", "Shares", "P&L", "Days"].map((h) => (
                      <th
                        key={h}
                        style={{
                          textAlign: h === "Ticker" ? "left" : "right",
                          padding: "var(--space-sm) var(--space-md)",
                          color: "var(--color-text-muted)",
                          fontWeight: 500, fontSize: "var(--text-xs)",
                          textTransform: "uppercase", letterSpacing: "0.05em",
                          borderBottom: "1px solid var(--glass-border)",
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {closedPositions.map((cp) => (
                    <tr key={cp.id}>
                      <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", fontWeight: 600 }}>
                        {cp.ticker}
                      </td>
                      <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        ${cp.entryPrice.toFixed(2)}
                      </td>
                      <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        {cp.exitPrice != null ? `$${cp.exitPrice.toFixed(2)}` : "—"}
                      </td>
                      <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        {cp.shares}
                      </td>
                      <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)", color: pnlColor(cp.realizedPnl) }}>
                        {formatCurrency(cp.realizedPnl)} ({formatPct(cp.realizedPnlPct)})
                      </td>
                      <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
                        {cp.holdingDays ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </BentoCard>
        )}

        {/* Bottom spacing for nav */}
        <div style={{ height: "var(--nav-height)" }} />
      </div>

      {/* Close Position Modal */}
      {closeTarget && (
        <ClosePositionModal
          position={closeTarget}
          onClose={() => setCloseTarget(null)}
          onSubmit={handleClose}
        />
      )}
    </div>
  );
}
