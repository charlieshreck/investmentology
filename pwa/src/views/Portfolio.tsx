import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { AnimatedNumber } from "../components/shared/AnimatedNumber";
import { FloatingBar } from "../components/shared/FloatingBar";
import { SegmentedControl } from "../components/shared/SegmentedControl";
import { MetricCardSkeleton, PositionRowSkeleton } from "../components/shared/SkeletonCard";
import { MarketStatus } from "../components/shared/MarketStatus";
import { GlossaryTooltip } from "../components/shared/GlossaryTooltip";
import { CorrelationHeatmap } from "../components/charts/CorrelationHeatmap";
import { Section } from "../components/shared/Section";
import { AllocationDonut } from "../components/charts/AllocationDonut";
import { PortfolioPerformanceChart } from "../components/charts/PortfolioPerformanceChart";
import { PositionCard } from "../components/portfolio/PositionCard";
import { DividendCard } from "../components/portfolio/DividendCard";
import { ClosedTradeCard } from "../components/portfolio/ClosedTradeCard";
import { ClosePositionModal } from "../components/portfolio/ClosePositionModal";
import { formatCurrency, formatPct, pnlColor, pnlGradientClass, alertVariant } from "../utils/format";
import { usePortfolio } from "../hooks/usePortfolio";
import { usePortfolioBalance } from "../hooks/usePortfolioBalance";
import { useCorrelations } from "../hooks/useCorrelations";
import { useConfetti } from "../hooks/useConfetti";
import { useWebSocket } from "../hooks/useWebSocket";
import { useAnalysis } from "../contexts/AnalysisContext";
import { useThesisSummary, usePortfolioRisk } from "../hooks/useToday";
import type { Position } from "../types/models";
import { useStore } from "../stores/useStore";
import {
  TrendingUp, TrendingDown, DollarSign, Wallet,
  AlertTriangle, BarChart3,
  ShieldAlert, Sparkles, PieChart,
} from "lucide-react";




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
  const { startAnalysis, isRunning: analysisRunning } = useAnalysis();
  const [closeTarget, setCloseTarget] = useState<Position | null>(null);
  const [closeStatus, setCloseStatus] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<BriefingSummary | null>(null);
  const [_corrOpen, _setCorrOpen] = useState(false);
  const [posFilter, setPosFilter] = useState("all");
  const [activeTab, setActiveTab] = useState("positions");
  const { positions: thesisPositions, loading: thesisLoading } = useThesisSummary();
  const { data: riskData, loading: riskLoading } = usePortfolioRisk();
  const { data: balance } = usePortfolioBalance(positions.length);
  const scrollRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const [showFloatingBar, setShowFloatingBar] = useState(false);

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

  // Show floating bar when hero scrolls out of view
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handler = () => {
      const heroBottom = heroRef.current?.getBoundingClientRect().bottom ?? 999;
      setShowFloatingBar(heroBottom < 0);
    };
    el.addEventListener("scroll", handler, { passive: true });
    return () => el.removeEventListener("scroll", handler);
  }, []);

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

  const fmtCurrencyStable = useCallback((n: number) => formatCurrency(n), []);
  const fmtPctStable = useCallback((n: number) => formatPct(n), []);

  /* ── Loading skeleton ── */
  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader />
        <div style={{ padding: "var(--space-xl)", display: "flex", flexDirection: "column", gap: "var(--space-xl)" }}>
          <div className="skeleton" style={{ height: 140, borderRadius: "var(--radius-xl)" }} />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
            <MetricCardSkeleton />
            <MetricCardSkeleton />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            <PositionRowSkeleton />
            <PositionRowSkeleton />
            <PositionRowSkeleton />
            <PositionRowSkeleton />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "var(--space-xl)", paddingTop: "calc(var(--header-height) + var(--space-xl))" }}>
        <ViewHeader />
        <BentoCard>
          <p style={{ color: "var(--color-error)" }}>Failed to load portfolio: {error}</p>
        </BentoCard>
      </div>
    );
  }

  // Merge live WebSocket prices
  const now = new Date();
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const enrichedPositions = positions.map((p) => {
    const live = livePrices[p.ticker];
    if (!live) return p;
    const livePrice = live.price;
    const mv = livePrice * p.shares;
    const cost = p.avgCost * p.shares;
    const pnl = mv - cost;
    const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
    // For same-day buys, "today" should match "since buy" — the WS changePct
    // uses yesterday's close which creates a misleading discrepancy.
    const boughtToday = p.entryDate === todayStr;
    const dayChg = boughtToday ? pnl : live.change * p.shares;
    const dayChgPct = boughtToday ? pnlPct : live.changePct;
    return {
      ...p,
      currentPrice: livePrice,
      marketValue: mv,
      unrealizedPnl: pnl,
      unrealizedPnlPct: pnlPct,
      dayChange: dayChg,
      dayChangePct: dayChgPct,
    };
  });

  const totalPnl = enrichedPositions.reduce((s, p) => s + p.unrealizedPnl, 0);
  const enrichedTotalValue = enrichedPositions.reduce((s, p) => s + p.marketValue, 0) + cash;
  const costBasis = enrichedTotalValue - totalPnl - cash;
  const totalPnlPct = costBasis > 0 ? (totalPnl / costBasis) * 100 : 0;
  const cashPct = enrichedTotalValue > 0 ? (cash / enrichedTotalValue) * 100 : 0;
  const enrichedDayPnl = enrichedPositions.reduce((s, p) => s + (p.dayChange || 0), 0);
  const liveDayPnl = Object.keys(livePrices).length > 0 ? enrichedDayPnl : dayPnl;
  const liveDayPnlPct = Object.keys(livePrices).length > 0 && enrichedTotalValue > 0
    ? (enrichedDayPnl / (enrichedTotalValue - enrichedDayPnl)) * 100
    : dayPnlPct;

  // Filter positions
  const winnersCount = enrichedPositions.filter(p => p.unrealizedPnl > 0).length;
  const losersCount = enrichedPositions.filter(p => p.unrealizedPnl < 0).length;
  const dividendPositions = enrichedPositions.filter(p => (p.annualDividend ?? 0) > 0);
  const totalMonthlyDiv = enrichedPositions.reduce((s, p) => s + (p.monthlyDividend || 0), 0);
  const totalAnnualDiv = enrichedPositions.reduce((s, p) => s + (p.annualDividend || 0), 0);
  const filteredPositions = posFilter === "all" ? enrichedPositions
    : posFilter === "winners" ? enrichedPositions.filter(p => p.unrealizedPnl > 0)
    : posFilter === "losers" ? enrichedPositions.filter(p => p.unrealizedPnl <= 0)
    : []; // dividends handled separately

  return (
    <div ref={scrollRef} style={{ height: "100%", overflowY: "auto" }}>
      {/* Floating portfolio summary bar */}
      <FloatingBar
        visible={showFloatingBar}
        totalValue={formatCurrency(enrichedTotalValue || totalValue)}
        dayPnl={liveDayPnl}
        dayPnlFormatted={`${formatCurrency(liveDayPnl)} (${formatPct(liveDayPnlPct)})`}
        positionCount={positions.length}
      />

      <ViewHeader
        subtitle={`${positions.length} positions`}
        tabs={[
          { key: "positions", label: "Positions" },
          { key: "thesis", label: "Thesis" },
          { key: "risk", label: "Risk" },
          { key: "history", label: "History" },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        right={
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
            {positions.length > 0 && activeTab === "positions" && (
              <button
                onClick={() => { if (!analysisRunning) startAnalysis(positions.map((p) => p.ticker)); }}
                disabled={analysisRunning}
                style={{
                  padding: "8px 16px",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  background: analysisRunning ? "var(--color-surface-2)" : "var(--gradient-active)",
                  color: analysisRunning ? "var(--color-text-muted)" : "#fff",
                  border: "none",
                  borderRadius: "var(--radius-full)",
                  cursor: analysisRunning ? "not-allowed" : "pointer",
                  whiteSpace: "nowrap",
                  letterSpacing: "0.02em",
                }}
              >
                {analysisRunning ? "Running..." : "Re-analyze All"}
              </button>
            )}
            <MarketStatus wsStatus={wsStatus} />
          </div>
        }
      />

      <div style={{ padding: "var(--space-xl)", display: "flex", flexDirection: "column", gap: "var(--space-xl)" }}>

        {/* ═══════ Positions Tab ═══════ */}
        {activeTab === "positions" && <>

        {/* ═══════ HERO: Total Value ═══════ */}
        <motion.div
          ref={heroRef}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          style={{
            padding: "var(--space-2xl) var(--space-xl)",
            background: "linear-gradient(135deg, var(--color-surface-0) 0%, rgba(99,102,241,0.08) 100%)",
            borderRadius: "var(--radius-xl)",
            border: "1px solid rgba(99,102,241,0.12)",
            boxShadow: "var(--shadow-card), 0 0 80px rgba(99,102,241,0.06), inset 0 1px 0 rgba(255,255,255,0.04)",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Decorative orb glows */}
          <div style={{
            position: "absolute",
            top: "-40%",
            left: "50%",
            transform: "translateX(-50%)",
            width: "120%",
            height: "100%",
            background: "radial-gradient(ellipse at center, rgba(99,102,241,0.10) 0%, transparent 60%)",
            pointerEvents: "none",
          }} />
          <div className="orb-glow" style={{
            top: "-20%",
            right: "-10%",
            width: "40%",
            height: "60%",
            background: "var(--color-accent-glow)",
          }} />
          <div className="orb-glow" style={{
            bottom: "-30%",
            left: "-5%",
            width: "35%",
            height: "50%",
            background: "var(--color-accent-ghost)",
          }} />

          <div style={{
            fontSize: "var(--text-xs)",
            fontWeight: 600,
            color: "var(--color-accent-bright)",
            textTransform: "uppercase",
            letterSpacing: "0.12em",
            marginBottom: "var(--space-md)",
            position: "relative",
          }}>
            Total Portfolio Value
          </div>

          <div style={{ position: "relative" }}>
            <AnimatedNumber
              value={enrichedTotalValue || totalValue}
              format={fmtCurrencyStable}
              className="text-gradient"
              style={{
                fontSize: "var(--text-4xl)",
                fontWeight: 800,
                fontFamily: "var(--font-mono)",
                letterSpacing: "-0.02em",
                lineHeight: 1.1,
              }}
            />
          </div>

          {/* Day P&L strip */}
          <div style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: "var(--space-md)",
            marginTop: "var(--space-lg)",
            position: "relative",
          }}>
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "var(--space-xs)",
              padding: "6px 16px",
              borderRadius: "var(--radius-full)",
              background: liveDayPnl >= 0 ? "var(--color-success-glow)" : "var(--color-error-glow)",
            }}>
              {liveDayPnl >= 0 ? <TrendingUp size={14} color="var(--color-success)" /> : <TrendingDown size={14} color="var(--color-error)" />}
              <AnimatedNumber
                value={liveDayPnl}
                format={fmtCurrencyStable}
                style={{
                  fontSize: "var(--text-sm)",
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  color: pnlColor(liveDayPnl),
                }}
              />
              <AnimatedNumber
                value={liveDayPnlPct}
                format={fmtPctStable}
                style={{
                  fontSize: "var(--text-xs)",
                  fontFamily: "var(--font-mono)",
                  color: pnlColor(liveDayPnlPct),
                  opacity: 0.8,
                }}
              />
            </div>
          </div>
        </motion.div>

        {/* ═══════ Metric Cards ═══════ */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "var(--space-md)",
        }}>
          <BentoCard title="Total P&L" delay={0.05} variant={totalPnl >= 0 ? "success" : "error"} compact glow>
            <AnimatedNumber
              value={totalPnl}
              format={fmtCurrencyStable}
              className={pnlGradientClass(totalPnl)}
              style={{ fontSize: "var(--text-2xl)", fontWeight: 800, fontFamily: "var(--font-mono)" }}
            />
            <AnimatedNumber
              value={totalPnlPct}
              format={fmtPctStable}
              style={{ fontSize: "var(--text-sm)", color: pnlColor(totalPnlPct), marginTop: 4 }}
            />
          </BentoCard>
          <BentoCard title="Cash" delay={0.1} compact>
            <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-sm)" }}>
              <Wallet size={16} color="var(--color-text-muted)" style={{ marginTop: 2 }} />
              <AnimatedNumber
                value={cash}
                format={fmtCurrencyStable}
                style={{ fontSize: "var(--text-2xl)", fontWeight: 800, fontFamily: "var(--font-mono)" }}
              />
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
              {cashPct.toFixed(1)}% of portfolio
            </div>
          </BentoCard>
        </div>

        {/* ═══════ Allocation ═══════ */}
        {enrichedPositions.length > 0 && (() => {
          const equitiesValue = enrichedPositions.reduce((s, p) => s + p.marketValue, 0);
          const allocationData = [
            { label: "Equities", value: equitiesValue, color: "var(--color-accent)" },
            ...(cash > 0 ? [{ label: "Cash", value: cash, color: "var(--color-text-muted)" }] : []),
          ];
          const targetAllocation = [
            { label: "Equities", value: 70, color: "var(--color-accent)" },
            { label: "Bonds", value: 15, color: "#60a5fa" },
            { label: "Gold", value: 10, color: "#fbbf24" },
            { label: "Cash", value: 5, color: "var(--color-text-muted)" },
          ];
          return (
            <Section title="Allocation" icon={PieChart} defaultOpen={false}>
              <div style={{
                display: "grid", gridTemplateColumns: "1fr 1fr",
                gap: "var(--space-lg)", alignItems: "start",
              }}>
                {/* Current */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-sm)" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Current
                  </div>
                  <AllocationDonut data={allocationData} size={140} />
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, width: "100%" }}>
                    {allocationData.map((d) => (
                      <div key={d.label} style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", fontSize: "var(--text-xs)" }}>
                        <div style={{ width: 8, height: 8, borderRadius: 2, background: d.color, flexShrink: 0 }} />
                        <span style={{ color: "var(--color-text-secondary)", flex: 1 }}>{d.label}</span>
                        <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text)", fontWeight: 600 }}>
                          {((d.value / (equitiesValue + cash)) * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Target */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-sm)" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Target
                  </div>
                  <AllocationDonut data={targetAllocation} size={140} />
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, width: "100%" }}>
                    {targetAllocation.map((d) => (
                      <div key={d.label} style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", fontSize: "var(--text-xs)" }}>
                        <div style={{ width: 8, height: 8, borderRadius: 2, background: d.color, flexShrink: 0 }} />
                        <span style={{ color: "var(--color-text-secondary)", flex: 1 }}>{d.label}</span>
                        <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text)", fontWeight: 600 }}>
                          {d.value}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Section>
          );
        })()}

        {/* ═══════ Performance ═══════ */}
        {performance && (
          <Section title="Performance" icon={BarChart3}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: "var(--space-sm)" }}>
              {[
                { label: "Alpha", value: performance.alphaPct, fmt: (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`, color: performance.alphaPct != null ? pnlColor(performance.alphaPct) : undefined, glossary: "alpha" },
                { label: "Sharpe", value: performance.sharpeRatio, fmt: (v: number) => v.toFixed(2), glossary: "sharpe ratio" },
                { label: "Sortino", value: performance.sortinoRatio, fmt: (v: number) => v.toFixed(2), glossary: "sortino ratio" },
                { label: "Win Rate", value: performance.winRate, fmt: (v: number) => `${(v * 100).toFixed(0)}%`, glossary: "win rate" },
                { label: "Max DD", value: performance.maxDrawdownPct, fmt: (v: number) => `${v.toFixed(1)}%`, color: "var(--color-error)", glossary: "max drawdown" },
              ].map((m) => (
                <div
                  key={m.label}
                  style={{
                    padding: "var(--space-md) var(--space-lg)",
                    background: "var(--color-surface-0)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--glass-border)",
                  }}
                >
                  <div style={{ fontSize: "var(--text-2xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4, display: "flex", alignItems: "center", gap: 2 }}>
                    {m.label}
                    {(m as { glossary?: string }).glossary && <GlossaryTooltip term={(m as { glossary?: string }).glossary!} />}
                  </div>
                  <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: m.color }}>
                    {m.value != null ? m.fmt(m.value) : "—"}
                  </div>
                </div>
              ))}
            </div>
            {/* Extended metrics (from PortfolioPerformanceExtended) */}
            {(performance.expectancy != null || performance.avgWinPct != null || performance.portfolioReturnPct != null) && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: "var(--space-sm)", marginTop: "var(--space-sm)" }}>
                {([
                  performance.portfolioReturnPct != null && { label: "Return", value: `${performance.portfolioReturnPct >= 0 ? "+" : ""}${performance.portfolioReturnPct.toFixed(1)}%`, color: pnlColor(performance.portfolioReturnPct) },
                  performance.spyReturnPct != null && { label: "SPY Return", value: `${performance.spyReturnPct! >= 0 ? "+" : ""}${performance.spyReturnPct!.toFixed(1)}%`, color: pnlColor(performance.spyReturnPct!) },
                  performance.expectancy != null && { label: "Expectancy", value: `${performance.expectancy >= 0 ? "+" : ""}${performance.expectancy.toFixed(2)}%`, color: pnlColor(performance.expectancy), glossary: "expectancy" },
                  performance.avgWinPct != null && { label: "Avg Win", value: `+${performance.avgWinPct.toFixed(1)}%`, color: "var(--color-success)" },
                  performance.avgLossPct != null && { label: "Avg Loss", value: `${performance.avgLossPct.toFixed(1)}%`, color: "var(--color-error)" },
                  performance.dispositionRatio != null && { label: "Disposition", value: performance.dispositionRatio.toFixed(2), glossary: "disposition ratio" },
                  performance.totalTrades != null && { label: "Trades", value: String(performance.totalTrades) },
                  performance.measurementDays != null && { label: "Days", value: String(performance.measurementDays) },
                ] as (false | { label: string; value: string; color?: string; glossary?: string })[])
                  .filter(Boolean)
                  .map((m) => {
                    const item = m as { label: string; value: string; color?: string; glossary?: string };
                    return (
                      <div key={item.label} style={{
                        padding: "var(--space-sm) var(--space-md)",
                        background: "var(--color-surface-0)",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--glass-border)",
                      }}>
                        <div style={{ fontSize: 9, color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2, display: "flex", alignItems: "center", gap: 2 }}>
                          {item.label}
                          {item.glossary && <GlossaryTooltip term={item.glossary} />}
                        </div>
                        <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, fontFamily: "var(--font-mono)", color: item.color }}>
                          {item.value}
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </Section>
        )}

        {/* ═══════ Daily Intelligence ═══════ */}
        {briefing && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            style={{
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
              border: "1px solid var(--glass-border)",
              background: "var(--color-surface-0)",
            }}
          >
            {/* Header strip with gradient */}
            <div style={{
              padding: "var(--space-md) var(--space-lg)",
              background: "var(--gradient-surface)",
              borderBottom: "1px solid var(--glass-border)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
            }}>
              <Sparkles size={14} color="var(--color-accent-bright)" />
              <span style={{
                fontSize: "var(--text-xs)",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--color-accent-bright)",
              }}>
                Daily Intel
              </span>
              <span style={{
                fontSize: 9,
                color: "var(--color-text-muted)",
                fontFamily: "var(--font-mono)",
                marginLeft: "auto",
              }}>
                {new Date(briefing.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
              </span>
            </div>

            {/* Pendulum + Risk + Stats row */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 1,
              background: "var(--glass-border)",
            }}>
              {/* Pendulum gauge */}
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", textAlign: "center" }}>
                <div style={{ position: "relative", width: 48, height: 28, margin: "0 auto 4px" }}>
                  <svg viewBox="0 0 48 28" style={{ width: "100%", height: "100%", overflow: "visible" }}>
                    {/* Gauge track */}
                    <path d="M 4 26 A 20 20 0 0 1 44 26" fill="none" stroke="var(--color-surface-2)" strokeWidth="4" strokeLinecap="round" />
                    {/* Gauge fill — position based on pendulumScore (0=fear, 100=greed) */}
                    <path
                      d="M 4 26 A 20 20 0 0 1 44 26"
                      fill="none"
                      stroke={briefing.pendulumScore <= 30 ? "var(--color-success)" : briefing.pendulumScore <= 60 ? "var(--color-warning)" : "var(--color-error)"}
                      strokeWidth="4"
                      strokeLinecap="round"
                      strokeDasharray={`${(briefing.pendulumScore / 100) * 63} 63`}
                    />
                    {/* Needle */}
                    {(() => {
                      const angle = Math.PI - (briefing.pendulumScore / 100) * Math.PI;
                      const nx = 24 + 16 * Math.cos(angle);
                      const ny = 26 - 16 * Math.sin(angle);
                      return <circle cx={nx} cy={ny} r="2.5" fill="var(--color-text)" stroke="var(--color-surface-0)" strokeWidth="1" />;
                    })()}
                  </svg>
                </div>
                <div style={{
                  fontSize: "var(--text-xs)", fontWeight: 800, textTransform: "capitalize",
                  color: briefing.pendulumScore <= 30 ? "var(--color-success)" : briefing.pendulumScore <= 60 ? "var(--color-warning)" : "var(--color-error)",
                }}>
                  {briefing.pendulumLabel}
                </div>
                <div style={{ fontSize: 8, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
                  Sentiment
                </div>
              </div>

              {/* Risk level */}
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", textAlign: "center" }}>
                <motion.div
                  animate={{ scale: [1, 1.15, 1] }}
                  transition={{ repeat: Infinity, duration: 2.5, ease: "easeInOut" }}
                  style={{ marginBottom: 4 }}
                >
                  <ShieldAlert
                    size={22}
                    color={briefing.overallRiskLevel === "low" ? "var(--color-success)" : briefing.overallRiskLevel === "elevated" ? "var(--color-warning)" : "var(--color-error)"}
                    style={{ margin: "0 auto" }}
                  />
                </motion.div>
                <div style={{
                  fontSize: "var(--text-xs)", fontWeight: 800, textTransform: "capitalize",
                  color: briefing.overallRiskLevel === "low" ? "var(--color-success)" : briefing.overallRiskLevel === "elevated" ? "var(--color-warning)" : "var(--color-error)",
                }}>
                  {briefing.overallRiskLevel}
                </div>
                <div style={{ fontSize: 8, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
                  Risk Level
                </div>
              </div>

              {/* Alerts */}
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", textAlign: "center" }}>
                <div style={{
                  fontSize: "var(--text-xl)", fontWeight: 800, fontFamily: "var(--font-mono)",
                  color: briefing.alertCount > 0 ? "var(--color-warning)" : "var(--color-text-muted)",
                }}>
                  {briefing.alertCount}
                </div>
                <div style={{ fontSize: 8, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
                  {briefing.alertCount === 1 ? "Alert" : "Alerts"}
                </div>
              </div>
            </div>

          </motion.div>
        )}

        {/* ═══════ Performance Chart ═══════ */}
        {positions.length > 0 && (
          <Section title="Performance" icon={TrendingUp} defaultOpen={false}>
            <div style={{
              padding: "var(--space-md) var(--space-lg)",
              background: "var(--color-surface-0)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--glass-border)",
            }}>
              <PortfolioPerformanceChart />
            </div>
          </Section>
        )}

        {/* ═══════ Positions (with Dividends tab) ═══════ */}
        <Section title="Positions" icon={DollarSign} count={enrichedPositions.length} defaultOpen={true}>
          <div style={{ marginBottom: "var(--space-md)" }}>
            <SegmentedControl
              segments={[
                { id: "all", label: "All", count: enrichedPositions.length },
                { id: "winners", label: "Winners", count: winnersCount },
                { id: "losers", label: "Losers", count: losersCount },
                ...(totalAnnualDiv > 0 ? [{ id: "dividends", label: "Dividends", count: dividendPositions.length }] : []),
              ]}
              activeId={posFilter}
              onChange={setPosFilter}
            />
          </div>

          <AnimatePresence mode="wait">
            {posFilter === "dividends" ? (
              <motion.div
                key="dividends"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                {/* Dividend totals banner */}
                <div style={{
                  display: "flex",
                  gap: "var(--space-sm)",
                  marginBottom: "var(--space-md)",
                }}>
                  {[
                    { label: "Monthly", value: formatCurrency(totalMonthlyDiv) },
                    { label: "Annual", value: formatCurrency(totalAnnualDiv) },
                  ].map((m) => (
                    <div key={m.label} style={{
                      flex: 1,
                      padding: "var(--space-md)",
                      background: "rgba(52,211,153,0.06)",
                      border: "1px solid rgba(52,211,153,0.15)",
                      borderRadius: "var(--radius-md)",
                      textAlign: "center",
                    }}>
                      <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4, fontWeight: 600 }}>{m.label}</div>
                      <div className="text-gradient-success" style={{ fontSize: "var(--text-lg)", fontWeight: 800, fontFamily: "var(--font-mono)" }}>
                        {m.value}
                      </div>
                    </div>
                  ))}
                </div>
                {/* Dividend cards */}
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                  {dividendPositions.map((p: any, i: number) => (
                    <motion.div
                      key={p.ticker}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.04, duration: 0.3 }}
                    >
                      <DividendCard position={p} />
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div
                key={posFilter}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
              >
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-sm)",
                  perspective: 1200,
                  perspectiveOrigin: "center top",
                }}>
                  {filteredPositions.map((p, i) => (
                    <motion.div
                      key={p.ticker}
                      initial={{
                        opacity: 0,
                        rotateX: -70,
                        scaleY: 0.4,
                        y: -30 * Math.min(i, 6),
                      }}
                      animate={{
                        opacity: 1,
                        rotateX: 0,
                        scaleY: 1,
                        y: 0,
                      }}
                      transition={{
                        delay: 0.3 + i * 0.08,
                        duration: 0.55,
                        ease: [0.22, 1, 0.36, 1],
                      }}
                      style={{
                        transformOrigin: "top center",
                        transformStyle: "preserve-3d",
                      }}
                    >
                      <PositionCard
                        position={p}
                        onClick={() => setOverlayTicker(p.ticker)}
                        onClose={() => setCloseTarget(p)}
                      />
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </Section>

        {/* ═══════ Balance ═══════ */}
        {balance && balance.sectors.length > 0 && (
          <Section title="Balance" defaultOpen={false}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>

              {/* Exploded pie + health badge */}
              <div style={{
                position: "relative",
                padding: "var(--space-lg)",
                background: "var(--color-surface-0)",
                borderRadius: "var(--radius-lg)",
                border: "1px solid var(--glass-border)",
              }}>
                {/* Health badge top-right */}
                <div style={{ position: "absolute", top: 12, right: 12, zIndex: 2 }}>
                  <Badge
                    variant={balance.health === "excellent" || balance.health === "good" ? "success" : balance.health === "fair" ? "warning" : "error"}
                    size="lg"
                  >
                    {balance.health}
                  </Badge>
                </div>

                {/* 3D Pie chart centered */}
                <div style={{
                  display: "flex", justifyContent: "center", marginBottom: "var(--space-lg)",
                  perspective: 600,
                }}>
                  <motion.div
                    initial={{ rotateX: 0, scale: 0.9, opacity: 0 }}
                    animate={{ rotateX: 45, scale: 1, opacity: 1 }}
                    transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                    style={{
                      position: "relative", width: 200, height: 200,
                      transformStyle: "preserve-3d",
                    }}
                  >
                    {/* Drop shadow layer beneath the pie */}
                    <div style={{
                      position: "absolute", inset: "15%",
                      borderRadius: "50%",
                      background: "radial-gradient(ellipse, rgba(0,0,0,0.4) 0%, transparent 70%)",
                      transform: "translateZ(-8px) translateY(12px) scaleY(0.6)",
                      filter: "blur(8px)",
                    }} />

                    {/* Thickness / side ring — simulates 3D depth */}
                    <svg viewBox="0 0 100 100" style={{
                      position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible",
                      transform: "translateZ(-4px)",
                    }}>
                      {(() => {
                        const cx = 50, cy = 50, r = 40;
                        let startAngle = -90;
                        const SECTOR_COLORS: Record<string, string> = {
                          Technology: "#3b82f6", "Basic Materials": "#f59e0b", Utilities: "#10b981",
                          "Consumer Defensive": "#06b6d4", Healthcare: "#ec4899", "Financial Services": "#8b5cf6",
                          "Consumer Cyclical": "#f97316", Energy: "#ef4444", Industrials: "#64748b",
                          "Communication Services": "#14b8a6", "Real Estate": "#a855f7",
                        };
                        return balance.sectors.map((s, i) => {
                          const angle = (s.pct / 100) * 360;
                          const endAngle = startAngle + angle;
                          const midAngle = startAngle + angle / 2;
                          const midRad = (midAngle * Math.PI) / 180;
                          const color = SECTOR_COLORS[s.name] || s.color || `hsl(${i * 72}, 65%, 55%)`;
                          const zone = s.pct <= s.softMax ? "green" : s.pct <= s.warnMax ? "amber" : "red";
                          const explode = zone !== "green" ? 3.5 : 0.8;
                          const offsetX = Math.cos(midRad) * explode;
                          const offsetY = Math.sin(midRad) * explode;
                          const largeArc = angle > 180 ? 1 : 0;
                          const startRad = (startAngle * Math.PI) / 180;
                          const endRad = (endAngle * Math.PI) / 180;
                          const x1 = cx + offsetX + r * Math.cos(startRad);
                          const y1 = cy + offsetY + r * Math.sin(startRad);
                          const x2 = cx + offsetX + r * Math.cos(endRad);
                          const y2 = cy + offsetY + r * Math.sin(endRad);
                          const path = `M ${cx + offsetX} ${cy + offsetY} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;
                          startAngle = endAngle;
                          return (
                            <path
                              key={`rim-${s.name}`}
                              d={path}
                              fill={color}
                              opacity={0.3}
                              stroke="rgba(0,0,0,0.3)"
                              strokeWidth="0.5"
                            />
                          );
                        });
                      })()}
                      <circle cx="50" cy="50" r="20" fill="var(--color-surface-0)" opacity="0.5" />
                    </svg>

                    {/* Main pie face */}
                    <svg viewBox="0 0 100 100" style={{
                      position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible",
                      filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.3))",
                    }}>
                      <defs>
                        {/* Glossy highlight overlay */}
                        <radialGradient id="pie-gloss" cx="35%" cy="30%" r="60%">
                          <stop offset="0%" stopColor="rgba(255,255,255,0.25)" />
                          <stop offset="50%" stopColor="rgba(255,255,255,0.08)" />
                          <stop offset="100%" stopColor="rgba(0,0,0,0.15)" />
                        </radialGradient>
                        {/* Per-sector gradient defs generated inline */}
                        {balance.sectors.map((s, i) => {
                          const SECTOR_COLORS: Record<string, string> = {
                            Technology: "#3b82f6", "Basic Materials": "#f59e0b", Utilities: "#10b981",
                            "Consumer Defensive": "#06b6d4", Healthcare: "#ec4899", "Financial Services": "#8b5cf6",
                            "Consumer Cyclical": "#f97316", Energy: "#ef4444", Industrials: "#64748b",
                            "Communication Services": "#14b8a6", "Real Estate": "#a855f7",
                          };
                          const color = SECTOR_COLORS[s.name] || s.color || `hsl(${i * 72}, 65%, 55%)`;
                          return (
                            <linearGradient key={`grad-${i}`} id={`sector-grad-${i}`} x1="0%" y1="0%" x2="100%" y2="100%">
                              <stop offset="0%" stopColor={color} stopOpacity="1" />
                              <stop offset="45%" stopColor={color} stopOpacity="0.85" />
                              <stop offset="100%" stopColor={color} stopOpacity="0.6" />
                            </linearGradient>
                          );
                        })}
                        {/* Inner shadow ring */}
                        <radialGradient id="inner-shadow" cx="50%" cy="50%" r="50%">
                          <stop offset="70%" stopColor="transparent" />
                          <stop offset="100%" stopColor="rgba(0,0,0,0.15)" />
                        </radialGradient>
                      </defs>

                      {(() => {
                        const cx = 50, cy = 50, r = 40;
                        let startAngle = -90;

                        return balance.sectors.map((s, i) => {
                          const angle = (s.pct / 100) * 360;
                          const endAngle = startAngle + angle;
                          const midAngle = startAngle + angle / 2;
                          const midRad = (midAngle * Math.PI) / 180;
                          const zone = s.pct <= s.softMax ? "green" : s.pct <= s.warnMax ? "amber" : "red";

                          const explode = zone !== "green" ? 3.5 : 0.8;
                          const offsetX = Math.cos(midRad) * explode;
                          const offsetY = Math.sin(midRad) * explode;

                          const largeArc = angle > 180 ? 1 : 0;
                          const startRad = (startAngle * Math.PI) / 180;
                          const endRad = (endAngle * Math.PI) / 180;
                          const x1 = cx + offsetX + r * Math.cos(startRad);
                          const y1 = cy + offsetY + r * Math.sin(startRad);
                          const x2 = cx + offsetX + r * Math.cos(endRad);
                          const y2 = cy + offsetY + r * Math.sin(endRad);

                          const path = `M ${cx + offsetX} ${cy + offsetY} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;

                          startAngle = endAngle;

                          return (
                            <motion.path
                              key={s.name}
                              d={path}
                              fill={`url(#sector-grad-${i})`}
                              stroke="rgba(0,0,0,0.25)"
                              strokeWidth="0.6"
                              initial={{ scale: 0.6, opacity: 0 }}
                              animate={{ scale: 1, opacity: 1 }}
                              transition={{ delay: 0.1 + i * 0.08, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                              style={{ transformOrigin: `${cx + offsetX}px ${cy + offsetY}px` }}
                            />
                          );
                        });
                      })()}

                      {/* Glossy highlight over entire pie */}
                      <circle cx="50" cy="50" r="40" fill="url(#pie-gloss)" pointerEvents="none" />

                      {/* Subtle inner ring shadow */}
                      <circle cx="50" cy="50" r="40" fill="url(#inner-shadow)" pointerEvents="none" />

                      {/* Center hole — glossy center disc */}
                      <circle cx="50" cy="50" r="21" fill="rgba(0,0,0,0.15)" />
                      <circle cx="50" cy="50" r="20" fill="var(--color-surface-0)" />
                      <circle cx="50" cy="50" r="20" fill="url(#pie-gloss)" opacity="0.4" />

                      {/* Outer rim highlight — catches light on the top edge */}
                      <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />
                    </svg>

                    {/* Center text — on top of everything */}
                    <div style={{
                      position: "absolute", inset: 0,
                      display: "flex", flexDirection: "column",
                      alignItems: "center", justifyContent: "center",
                      transform: "translateZ(2px)",
                    }}>
                      <div style={{ fontSize: "var(--text-lg)", fontWeight: 800, fontFamily: "var(--font-mono)", textShadow: "0 1px 4px rgba(0,0,0,0.5)" }}>
                        {balance.sectorCount}
                      </div>
                      <div style={{ fontSize: 9, color: "var(--color-text-muted)", marginTop: -2, textShadow: "0 1px 2px rgba(0,0,0,0.4)" }}>sectors</div>
                    </div>
                  </motion.div>
                </div>

                {/* Sector legend cards */}
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {balance.sectors.map((s, i) => {
                    const zone = s.pct <= s.softMax ? "green" : s.pct <= s.warnMax ? "amber" : "red";
                    const SECTOR_COLORS: Record<string, string> = {
                      Technology: "#3b82f6", "Basic Materials": "#f59e0b", Utilities: "#10b981",
                      "Consumer Defensive": "#06b6d4", Healthcare: "#ec4899", "Financial Services": "#8b5cf6",
                      "Consumer Cyclical": "#f97316", Energy: "#ef4444", Industrials: "#64748b",
                      "Communication Services": "#14b8a6", "Real Estate": "#a855f7",
                    };
                    const color = SECTOR_COLORS[s.name] || s.color || `hsl(${i * 72}, 65%, 55%)`;
                    const borderColor = zone === "red" ? "rgba(248,113,113,0.4)" : zone === "amber" ? "rgba(251,191,36,0.3)" : "var(--glass-border)";
                    const bgGlow = zone === "red" ? "rgba(248,113,113,0.06)" : zone === "amber" ? "rgba(251,191,36,0.04)" : "transparent";

                    return (
                      <motion.div
                        key={s.name}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.2 + i * 0.06 }}
                        style={{
                          display: "flex", alignItems: "center", gap: "var(--space-sm)",
                          padding: "8px var(--space-md)",
                          borderRadius: "var(--radius-sm)",
                          background: bgGlow,
                          border: `1px solid ${borderColor}`,
                        }}
                      >
                        <div style={{ width: 12, height: 12, borderRadius: 3, background: color, flexShrink: 0 }} />
                        <span style={{ flex: 1, fontSize: "var(--text-xs)", fontWeight: 600 }}>{s.name}</span>
                        <span style={{ fontSize: 9, color: "var(--color-text-muted)" }}>{s.tickers?.join(", ")}</span>

                        {/* Proportion bar */}
                        <div style={{ width: 50, height: 6, background: "var(--color-surface-2)", borderRadius: 3, overflow: "hidden", flexShrink: 0 }}>
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(s.pct / 50 * 100, 100)}%` }}
                            transition={{ delay: 0.3 + i * 0.06, duration: 0.5 }}
                            style={{
                              height: "100%", borderRadius: 3,
                              background: zone === "red" ? "var(--color-error)" : zone === "amber" ? "var(--color-warning)" : color,
                            }}
                          />
                        </div>

                        <span style={{
                          fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", fontWeight: 700,
                          minWidth: 35, textAlign: "right",
                          color: zone === "red" ? "var(--color-error)" : zone === "amber" ? "var(--color-warning)" : "var(--color-text-secondary)",
                        }}>
                          {s.pct.toFixed(0)}%
                        </span>

                        {zone !== "green" && (
                          <span style={{
                            fontSize: 8, fontWeight: 700, textTransform: "uppercase",
                            padding: "2px 6px", borderRadius: "var(--radius-full)",
                            background: zone === "red" ? "rgba(248,113,113,0.15)" : "rgba(251,191,36,0.12)",
                            color: zone === "red" ? "var(--color-error)" : "var(--color-warning)",
                            letterSpacing: "0.04em", flexShrink: 0,
                          }}>
                            {zone === "red" ? "Over" : "Watch"}
                          </span>
                        )}
                      </motion.div>
                    );
                  })}
                </div>
              </div>


              {/* Insights */}
              {balance.insights.length > 0 && (
                <div style={{
                  padding: "var(--space-md) var(--space-lg)",
                  background: "var(--color-surface-0)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--glass-border)",
                  borderLeft: `3px solid ${
                    balance.health === "excellent" || balance.health === "good" ? "var(--color-success)" :
                    balance.health === "fair" ? "var(--color-warning)" : "var(--color-error)"
                  }`,
                }}>
                  {balance.insights.map((insight, i) => (
                    <div key={i} style={{
                      fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.6,
                      marginBottom: i < balance.insights.length - 1 ? 6 : 0,
                    }}>
                      {insight}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Section>
        )}

        {/* ═══════ Correlation ═══════ */}
        {corrData && corrData.tickers.length >= 2 && corrData.correlations.length > 0 && (
          <Section title="Correlation Matrix" defaultOpen={false}>
            <BentoCard>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-lg)" }}>
                90-day pairwise price correlations
              </div>
              <CorrelationHeatmap tickers={corrData.tickers} correlations={corrData.correlations} />
            </BentoCard>
          </Section>
        )}

        {/* ═══════ Alerts ═══════ */}
        {alerts.length > 0 && (
          <Section title="Alerts" icon={AlertTriangle} count={alerts.length}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {alerts.map((a) => (
                <div
                  key={a.id}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "var(--space-md)",
                    padding: "var(--space-lg)",
                    borderRadius: "var(--radius-md)",
                    background: "var(--color-surface-0)",
                    border: "1px solid var(--glass-border)",
                  }}
                >
                  <Badge variant={alertVariant(a.severity)}>{a.severity}</Badge>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>
                      {a.ticker && <span style={{ color: "var(--color-accent-bright)", marginRight: "var(--space-sm)" }}>{a.ticker}</span>}
                      {a.title}
                    </div>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4, lineHeight: 1.5 }}>
                      {a.message}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        </>}

        {/* ═══════ Thesis Tab ═══════ */}
        {activeTab === "thesis" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            {thesisLoading ? (
              <div style={{ padding: "var(--space-xl)", textAlign: "center", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
                Loading thesis data...
              </div>
            ) : thesisPositions.length === 0 ? (
              <div style={{ padding: "var(--space-xl)", textAlign: "center", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
                No positions with thesis data yet
              </div>
            ) : thesisPositions.map((tp) => {
              const healthColors: Record<string, string> = {
                INTACT: "var(--color-success)",
                UNDER_REVIEW: "var(--color-warning)",
                CHALLENGED: "var(--color-error)",
                BROKEN: "var(--color-error)",
              };
              const healthCol = healthColors[tp.thesis_health] || "var(--color-text-muted)";
              const convictionPct = Math.max(0, Math.min(100, Math.round(tp.conviction_trend * 100)));
              return (
                <motion.div
                  key={tp.ticker}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  style={{
                    borderRadius: "var(--radius-lg)",
                    background: "var(--color-surface-0)",
                    border: "1px solid var(--glass-border)",
                    overflow: "hidden",
                    cursor: "pointer",
                  }}
                  onClick={() => setOverlayTicker(tp.ticker)}
                >
                  {/* Top accent */}
                  <div style={{ height: 2, background: healthCol, opacity: 0.5 }} />

                  <div style={{ padding: "var(--space-md) var(--space-lg)" }}>
                    {/* Row 1: Ticker + type + health badge */}
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: 6 }}>
                      <span style={{ fontWeight: 800, fontFamily: "var(--font-mono)", fontSize: "var(--text-base)" }}>
                        {tp.ticker}
                      </span>
                      <span style={{
                        fontSize: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em",
                        padding: "1px 6px", borderRadius: 4,
                        background: "rgba(99,102,241,0.12)", color: "var(--color-accent-bright)",
                      }}>
                        {tp.position_type}
                      </span>
                      <span style={{
                        fontSize: 10, fontWeight: 700, marginLeft: "auto",
                        color: healthCol,
                      }}>
                        {"\u25CF"} {tp.thesis_health.replace("_", " ")}
                      </span>
                    </div>

                    {/* Entry thesis */}
                    <div style={{
                      fontSize: "var(--text-xs)", color: "var(--color-text-secondary)",
                      fontStyle: "italic", lineHeight: 1.4, marginBottom: 8,
                    }}>
                      &ldquo;{tp.entry_thesis}&rdquo;
                    </div>

                    {/* Conviction bar + stats row */}
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
                      {/* Conviction bar */}
                      <div style={{ flex: 1 }}>
                        <div style={{
                          fontSize: 9, color: "var(--color-text-muted)", fontWeight: 600,
                          marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.06em",
                        }}>
                          Conviction
                        </div>
                        <div style={{
                          height: 6, borderRadius: 3, background: "var(--color-surface-2)",
                          overflow: "hidden",
                        }}>
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${convictionPct}%` }}
                            transition={{ duration: 0.6, ease: "easeOut" }}
                            style={{
                              height: "100%", borderRadius: 3,
                              background: convictionPct >= 70 ? "var(--color-success)" :
                                convictionPct >= 40 ? "var(--color-warning)" : "var(--color-error)",
                            }}
                          />
                        </div>
                      </div>

                      <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--color-text-muted)" }}>
                        {tp.days_held}d
                      </span>
                      <span style={{
                        fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 700,
                        color: tp.pnl_pct >= 0 ? "var(--color-success)" : "var(--color-error)",
                      }}>
                        {tp.pnl_pct >= 0 ? "+" : ""}{tp.pnl_pct.toFixed(1)}%
                      </span>
                    </div>

                    {/* Reasoning */}
                    {tp.reasoning && (
                      <div style={{
                        fontSize: 11, color: "var(--color-text-muted)", lineHeight: 1.4,
                        marginTop: 8,
                      }}>
                        {tp.reasoning}
                      </div>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}

        {/* ═══════ Risk Tab ═══════ */}
        {activeTab === "risk" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            {riskLoading ? (
              <div style={{ padding: "var(--space-xl)", textAlign: "center", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
                Loading risk data...
              </div>
            ) : !riskData ? (
              <div style={{ padding: "var(--space-xl)", textAlign: "center", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
                No risk data available
              </div>
            ) : (<>
              {/* Risk level badge */}
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                padding: "var(--space-xl)",
                background: "var(--color-surface-0)", borderRadius: "var(--radius-lg)",
                border: "1px solid var(--glass-border)",
              }}>
                <div style={{ textAlign: "center" }}>
                  <ShieldAlert
                    size={32}
                    color={
                      riskData.risk_level === "NORMAL" ? "var(--color-success)" :
                      riskData.risk_level === "ELEVATED" ? "var(--color-warning)" :
                      "var(--color-error)"
                    }
                  />
                  <div style={{
                    fontSize: "var(--text-lg)", fontWeight: 800, marginTop: 8,
                    color: riskData.risk_level === "NORMAL" ? "var(--color-success)" :
                      riskData.risk_level === "ELEVATED" ? "var(--color-warning)" :
                      "var(--color-error)",
                  }}>
                    {riskData.risk_level}
                  </div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
                    Overall Risk Level
                  </div>
                </div>
              </div>

              {/* Key metrics row */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-sm)" }}>
                {[
                  { label: "Top Weight", value: `${riskData.top_position_weight.toFixed(1)}%`, warn: riskData.top_position_weight > 20 },
                  { label: "Health Score", value: `${(riskData.avg_thesis_health_score * 100).toFixed(0)}%`, warn: riskData.avg_thesis_health_score < 0.7 },
                  { label: "Positions", value: `${riskData.position_count}`, warn: false },
                ].map((m) => (
                  <div key={m.label} style={{
                    padding: "var(--space-md)",
                    background: "var(--color-surface-0)", borderRadius: "var(--radius-md)",
                    border: "1px solid var(--glass-border)", textAlign: "center",
                  }}>
                    <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600, marginBottom: 4 }}>
                      {m.label}
                    </div>
                    <div style={{
                      fontSize: "var(--text-lg)", fontWeight: 800, fontFamily: "var(--font-mono)",
                      color: m.warn ? "var(--color-warning)" : "var(--color-text)",
                    }}>
                      {m.value}
                    </div>
                  </div>
                ))}
              </div>

              {/* Sector concentration bars */}
              {Object.keys(riskData.sector_concentration).length > 0 && (
                <div style={{
                  padding: "var(--space-lg)",
                  background: "var(--color-surface-0)", borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--glass-border)",
                }}>
                  <div style={{
                    fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)",
                    textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "var(--space-md)",
                  }}>
                    Sector Concentration
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {Object.entries(riskData.sector_concentration)
                      .sort(([, a], [, b]) => b - a)
                      .map(([sector, pct]) => (
                        <div key={sector}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                            <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{sector}</span>
                            <span style={{
                              fontSize: 11, fontFamily: "var(--font-mono)", fontWeight: 600,
                              color: pct > 30 ? "var(--color-warning)" : "var(--color-text-muted)",
                            }}>
                              {pct.toFixed(1)}%
                            </span>
                          </div>
                          <div style={{ height: 5, borderRadius: 3, background: "var(--color-surface-2)" }}>
                            <div style={{
                              height: "100%", borderRadius: 3,
                              width: `${Math.min(pct, 100)}%`,
                              background: pct > 30 ? "var(--color-warning)" :
                                pct > 20 ? "var(--color-accent)" : "var(--color-success)",
                              transition: "width 0.3s ease",
                            }} />
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* Position thesis health summary */}
              {riskData.positions.length > 0 && (
                <div style={{
                  padding: "var(--space-lg)",
                  background: "var(--color-surface-0)", borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--glass-border)",
                }}>
                  <div style={{
                    fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--color-text-secondary)",
                    textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "var(--space-md)",
                  }}>
                    Position Health
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {riskData.positions
                      .sort((a, b) => b.weight_pct - a.weight_pct)
                      .map((p) => {
                        const hCol: Record<string, string> = {
                          INTACT: "var(--color-success)", UNDER_REVIEW: "var(--color-warning)",
                          CHALLENGED: "var(--color-error)", BROKEN: "var(--color-error)",
                        };
                        return (
                          <div
                            key={p.ticker}
                            onClick={() => setOverlayTicker(p.ticker)}
                            style={{
                              display: "flex", alignItems: "center", gap: "var(--space-sm)",
                              padding: "6px var(--space-sm)", borderRadius: "var(--radius-sm)",
                              cursor: "pointer",
                            }}
                          >
                            <span style={{
                              width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                              background: hCol[p.thesis_health] || "var(--color-text-muted)",
                            }} />
                            <span style={{ fontWeight: 700, fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", minWidth: 44 }}>
                              {p.ticker}
                            </span>
                            <span style={{
                              fontSize: 10, color: "var(--color-text-muted)", flex: 1,
                            }}>
                              {p.weight_pct.toFixed(1)}% weight
                            </span>
                            <span style={{
                              fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
                              color: p.pnl_pct >= 0 ? "var(--color-success)" : "var(--color-error)",
                            }}>
                              {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct.toFixed(1)}%
                            </span>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}
            </>)}
          </div>
        )}

        {/* ═══════ History Tab ═══════ */}
        {activeTab === "history" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            {closedPositions.length === 0 ? (
              <div style={{ padding: "var(--space-xl)", textAlign: "center", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
                No closed trades yet
              </div>
            ) : (<>
              {/* Total realized banner */}
              <div style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "var(--space-md) var(--space-lg)",
                background: "var(--color-surface-0)", borderRadius: "var(--radius-md)",
                border: "1px solid var(--glass-border)",
              }}>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {closedPositions.length} trade{closedPositions.length !== 1 ? "s" : ""} realized
                </span>
                <span style={{ fontSize: "var(--text-base)", fontFamily: "var(--font-mono)", fontWeight: 700, color: pnlColor(totalRealizedPnl) }}>
                  {formatCurrency(totalRealizedPnl)}
                </span>
              </div>
              {/* Individual closed trade cards */}
              {closedPositions.map((cp) => (
                <ClosedTradeCard key={cp.id} trade={cp} />
              ))}
            </>)}
          </div>
        )}

        {/* Status toast */}
        <AnimatePresence>
          {closeStatus && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              style={{
                position: "fixed",
                bottom: "calc(var(--nav-height) + var(--space-lg))",
                left: "50%",
                transform: "translateX(-50%)",
                padding: "var(--space-md) var(--space-xl)",
                borderRadius: "var(--radius-full)",
                background: closeStatus.startsWith("Error") ? "var(--color-error)" : "var(--color-success)",
                color: "#fff",
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                boxShadow: "var(--shadow-elevated)",
                zIndex: 50,
              }}
            >
              {closeStatus}
            </motion.div>
          )}
        </AnimatePresence>

        <div style={{ height: "var(--nav-height)" }} />
      </div>

      {/* Close Position Modal */}
      <AnimatePresence>
        {closeTarget && (
          <ClosePositionModal
            position={closeTarget}
            onClose={() => setCloseTarget(null)}
            onSubmit={handleClose}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
