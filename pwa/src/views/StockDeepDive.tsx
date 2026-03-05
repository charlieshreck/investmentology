import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { BentoCard } from "../components/shared/BentoCard";
import { AddToPortfolioModal } from "../components/shared/AddToPortfolioModal";
import { ScenarioAnalysis } from "../components/portfolio/ScenarioAnalysis";
import { InteractiveChart } from "../components/charts/InteractiveChart";
import { MarketStatus } from "../components/shared/MarketStatus";
import { Badge } from "../components/shared/Badge";
import { formatCap } from "../utils/deepdiveHelpers";
import { useAnalysis } from "../contexts/AnalysisContext";
import { useStore } from "../stores/useStore";
import type { AdversarialResult, TargetPriceRange } from "../types/models";

// Layer 1
import { OrbitBorder } from "../components/shared/OrbitBorder";
import { HeroVerdictStrip } from "../components/deepdive/HeroVerdictStrip";
import { PositionTile } from "../components/deepdive/PositionTile";
import { SignalPills } from "../components/deepdive/SignalPills";
// Layer 2
import { AgentAnalysisPanel } from "../components/deepdive/AgentAnalysisPanel";
import { MetricsPanel } from "../components/deepdive/MetricsPanel";
import { RiskPanel } from "../components/deepdive/RiskPanel";
import { PositionPanel } from "../components/deepdive/PositionPanel";
import { CompetencePanel } from "../components/deepdive/CompetencePanel";
import { ResearchBriefingPanel } from "../components/deepdive/ResearchBriefingPanel";
import { CollapsiblePanel } from "../components/deepdive/CollapsiblePanel";
// Layer 3
import { ArchiveSection } from "../components/deepdive/ArchiveSection";

// ─── Exported interfaces (consumed by sub-components) ───────────────────────

export interface Fundamentals {
  market_cap: number;
  operating_income: number;
  revenue: number;
  net_income: number;
  total_debt: number;
  cash: number;
  shares_outstanding: number;
  price: number;
  earnings_yield: number | null;
  roic: number | null;
  enterprise_value: number;
  fetched_at: string;
}

export interface QuantGate {
  combinedRank: number;
  eyRank: number;
  roicRank: number;
  piotroskiScore: number;
  altmanZScore: number | null;
  altmanZone: string | null;
  compositeScore: number | null;
}

export interface Profile {
  sector: string | null;
  industry: string | null;
  businessSummary: string | null;
  website: string | null;
  employees: number | null;
  city: string | null;
  country: string | null;
  beta: number | null;
  dividendYield: number | null;
  trailingPE: number | null;
  forwardPE: number | null;
  priceToBook: number | null;
  priceToSales: number | null;
  fiftyTwoWeekHigh: number | null;
  fiftyTwoWeekLow: number | null;
  averageVolume: number | null;
  analystTarget: number | null;
  analystRecommendation: string | null;
  analystCount: number | null;
}

export interface Signal {
  agentName: string;
  model: string;
  signals: Record<string, unknown>;
  confidence: number | null;
  reasoning: string;
  createdAt: string;
}

export interface Decision {
  id: string;
  decisionType: string;
  layer: string;
  confidence: number | null;
  reasoning: string;
  createdAt: string;
  outcome?: string | null;
  settledAt?: string | null;
}

export interface AgentStance {
  name: string;
  sentiment: number;
  confidence: number;
  key_signals: string[];
  summary: string;
}

export interface AdvisoryOpinion {
  advisor_name: string;
  display_name: string;
  vote: string;
  confidence: number;
  assessment: string;
  key_concern: string | null;
  key_endorsement: string | null;
  reasoning: string;
}

export interface BoardNarrative {
  headline: string;
  narrative: string;
  risk_summary: string;
  pre_mortem: string;
  conflict_resolution: string;
  advisor_consensus: Record<string, unknown>;
}

export interface VerdictData {
  recommendation: string;
  confidence: number | null;
  consensusScore: number | null;
  reasoning: string;
  agentStances: AgentStance[] | null;
  riskFlags: string[] | null;
  auditorOverride: boolean;
  mungerOverride: boolean;
  advisoryOpinions: AdvisoryOpinion[] | null;
  boardNarrative: BoardNarrative | null;
  boardAdjustedVerdict: string | null;
  adversarialResult?: AdversarialResult | null;
  createdAt: string | null;
}

export interface MoatData {
  type: string;
  sources: string[];
  trajectory: string;
  durability_years: number;
  confidence: number;
  reasoning: string;
}

export interface CompetenceData {
  passed: boolean;
  confidence: number | null;
  reasoning: string;
  in_circle?: boolean;
  sector_familiarity?: string;
  moat?: MoatData | null;
}

export interface WatchlistInfo {
  state: string;
  notes: string | null;
  updated_at: string | null;
}

export interface NewsArticle {
  title: string;
  summary: string;
  publisher: string;
  url: string;
  published_at: string | null;
  type: string;
}

export interface BuzzData {
  buzzScore: number;
  buzzLabel: string;
  headlineSentiment: number | null;
  articleCount: number;
  contrarianFlag: boolean;
}

export interface EarningsMomentum {
  score: number;
  label: string;
  upwardRevisions: number;
  downwardRevisions: number;
  beatStreak: number;
}

export interface PositionData {
  id: string;
  shares: number;
  entryPrice: number;
  currentPrice: number;
  positionType: string;
  weight: number | null;
  stopLoss: number | null;
  fairValue: number | null;
  pnl: number;
  pnlPct: number;
  entryDate: string | null;
  thesis: string | null;
}

export interface BriefingData {
  headline: string;
  situation: string;
  action: string;
  rationale: string;
}

export interface ResearchBriefing {
  content: string;
  sourceCount: number;
  createdAt: string | null;
}

export interface StockResponse {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  profile: Profile | null;
  fundamentals: Fundamentals | null;
  quantGate: QuantGate | null;
  competence: CompetenceData | null;
  verdict: VerdictData | null;
  verdictHistory: VerdictData[];
  signals: Signal[];
  decisions: Decision[];
  watchlist: WatchlistInfo | null;
  position: PositionData | null;
  briefing: BriefingData | null;
  buzz: BuzzData | null;
  earningsMomentum: EarningsMomentum | null;
  stabilityScore: number | null;
  stabilityLabel: string | null;
  consensusTier: string | null;
  targetPriceRange: TargetPriceRange | null;
  researchBriefing: ResearchBriefing | null;
}

// ─── Orchestrator ───────────────────────────────────────────────────────────

function stateBadge(state: string) {
  const map: Record<string, "accent" | "success" | "warning" | "error" | "neutral"> = {
    CANDIDATE: "accent", CONVICTION_BUY: "success", POSITION_HOLD: "success",
    WATCHLIST_EARLY: "accent", WATCHLIST_CATALYST: "warning",
    REJECTED: "error", POSITION_SELL: "warning",
  };
  return <Badge variant={map[state] ?? "neutral"}>{state.replace(/_/g, " ")}</Badge>;
}

export function StockDeepDive({ ticker }: { ticker: string }) {
  const navigate = useNavigate();
  const [data, setData] = useState<StockResponse | null>(null);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addStatus, setAddStatus] = useState<string | null>(null);
  const [showPortfolioModal, setShowPortfolioModal] = useState(false);
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [showScenarioModal, setShowScenarioModal] = useState(false);
  const [closeExitPrice, setCloseExitPrice] = useState("");
  const [refetchKey, setRefetchKey] = useState(0);

  const refetchStock = useCallback(() => {
    setRefetchKey((k) => k + 1);
  }, []);

  const { startAnalysis, isRunning: analysisRunning } = useAnalysis();
  const analysisProgress = useStore((s) => s.analysisProgress);
  const isAnalyzing = analysisRunning && analysisProgress?.ticker === ticker;

  const wasAnalyzing = useRef(false);
  useEffect(() => {
    if (isAnalyzing) {
      wasAnalyzing.current = true;
    } else if (wasAnalyzing.current) {
      wasAnalyzing.current = false;
      refetchStock();
    }
  }, [isAnalyzing, refetchStock]);

  useEffect(() => {
    let cancelled = false;
    async function fetchStock() {
      try {
        setLoading(true);
        const res = await fetch(`/api/invest/stock/${ticker}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result: StockResponse = await res.json();
        if (!cancelled) { setData(result); setError(null); }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    async function fetchNews() {
      try {
        const res = await fetch(`/api/invest/stock/${ticker}/news`);
        if (res.ok) {
          const result = await res.json();
          if (!cancelled) setNews(result.articles || []);
        }
      } catch { /* news is optional */ }
    }
    fetchStock();
    fetchNews();
    return () => { cancelled = true; };
  }, [ticker, refetchKey]);

  const handleClosePosition = async () => {
    if (!data?.position?.id) return;
    const ep = parseFloat(closeExitPrice);
    if (isNaN(ep) || ep <= 0) return;
    try {
      const res = await fetch(`/api/invest/portfolio/positions/${data.position.id}/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exit_price: ep }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setShowCloseModal(false);
      setAddStatus("Position closed");
      setTimeout(() => setAddStatus(null), 3000);
      refetchStock();
    } catch (err) {
      setAddStatus(`Error: ${err instanceof Error ? err.message : "failed"}`);
      setTimeout(() => setAddStatus(null), 3000);
    }
  };

  // ─── Loading skeleton ────────────────────────────────────────────────────

  if (loading) return (
    <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div className="skeleton" style={{ height: 22, width: 100, borderRadius: "var(--radius-sm)" }} />
          <div className="skeleton" style={{ height: 14, width: 180, borderRadius: "var(--radius-sm)" }} />
          <div className="skeleton" style={{ height: 12, width: 140, borderRadius: "var(--radius-sm)" }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
          <div className="skeleton" style={{ height: 28, width: 80, borderRadius: "var(--radius-sm)" }} />
          <div className="skeleton" style={{ height: 12, width: 60, borderRadius: "var(--radius-sm)" }} />
        </div>
      </div>
      <div className="skeleton" style={{ height: 180, borderRadius: "var(--radius-lg)" }} />
      <div className="skeleton" style={{ height: 100, borderRadius: "var(--radius-lg)" }} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
        <div className="skeleton" style={{ height: 80, borderRadius: "var(--radius-md)" }} />
        <div className="skeleton" style={{ height: 80, borderRadius: "var(--radius-md)" }} />
      </div>
    </div>
  );

  // ─── Error state ─────────────────────────────────────────────────────────

  if (error || !data) return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      gap: "var(--space-lg)", padding: "var(--space-2xl) var(--space-xl)", textAlign: "center",
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: "50%",
        background: "rgba(248, 113, 113, 0.1)", border: "1px solid rgba(248, 113, 113, 0.2)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-error)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      </div>
      <div>
        <p style={{ margin: 0, fontSize: "var(--text-base)", fontWeight: 600, color: "var(--color-text-secondary)" }}>
          Couldn't load {ticker}
        </p>
        <p style={{ margin: "var(--space-sm) 0 0", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
          {error ?? "No data available"}
        </p>
      </div>
    </div>
  );

  const f = data.fundamentals;
  const p = data.profile;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
      {/* Status toast */}
      {addStatus && (
        <div style={{
          padding: "var(--space-sm) var(--space-lg)", borderRadius: "var(--radius-sm)",
          background: addStatus.startsWith("Error") ? "var(--color-error)" : "var(--color-success)",
          color: "#fff", fontSize: "var(--text-sm)", fontWeight: 500,
        }}>
          {addStatus}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          LAYER 1 — THE VERDICT (always visible, above fold)
         ═══════════════════════════════════════════════════════════════════ */}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
            <span style={{ fontSize: "var(--text-xl)", fontWeight: 700 }}>{data.ticker}</span>
            {data.watchlist && stateBadge(data.watchlist.state)}
          </div>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>{data.name}</div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-xs)", display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
            {data.industry && <span>{data.industry}</span>}
            {data.industry && data.sector && <span>/</span>}
            {data.sector && <span>{data.sector}</span>}
            {p?.city && p?.country && <span style={{ opacity: 0.7 }}>{p.city}, {p.country}</span>}
            {p?.website && (
              <a href={p.website} target="_blank" rel="noopener noreferrer" style={{ color: "var(--color-accent-bright)", textDecoration: "none" }}>
                {p.website.replace(/^https?:\/\/(www\.)?/, "")}
              </a>
            )}
          </div>
        </div>
        <div style={{ textAlign: "right", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "var(--space-xs)" }}>
          <MarketStatus />
          {f && <div style={{ fontSize: "var(--text-lg)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>${f.price.toFixed(2)}</div>}
          {f && <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>{formatCap(f.market_cap)}</div>}
          {p?.employees && <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>{p.employees.toLocaleString()} employees</div>}
          <div style={{ display: "flex", gap: "var(--space-sm)", marginTop: "var(--space-xs)" }}>
            <button
              onClick={() => { if (!analysisRunning) startAnalysis([ticker]); }}
              disabled={isAnalyzing}
              style={{
                padding: "var(--space-xs) var(--space-md)", borderRadius: "var(--radius-sm)",
                background: isAnalyzing ? "var(--color-surface-2)" : "var(--color-accent-ghost)",
                border: "none", color: isAnalyzing ? "var(--color-text-muted)" : "var(--color-accent-bright)",
                cursor: isAnalyzing ? "wait" : "pointer", fontSize: "var(--text-xs)", fontWeight: 600, whiteSpace: "nowrap",
              }}
            >
              {isAnalyzing ? "Analyzing..." : "Analyze"}
            </button>
            <button
              onClick={() => setShowPortfolioModal(true)}
              style={{
                padding: "var(--space-xs) var(--space-md)", borderRadius: "var(--radius-sm)",
                background: "var(--gradient-active)", border: "none", color: "#fff",
                cursor: "pointer", fontSize: "var(--text-xs)", fontWeight: 600, whiteSpace: "nowrap",
              }}
            >
              + Portfolio
            </button>
            <button
              onClick={() => setShowScenarioModal(true)}
              style={{
                padding: "var(--space-xs) var(--space-md)", borderRadius: "var(--radius-sm)",
                background: "var(--color-surface-1)", border: "1px solid var(--color-surface-2)",
                color: "var(--color-text-muted)",
                cursor: "pointer", fontSize: "var(--text-xs)", fontWeight: 600, whiteSpace: "nowrap",
              }}
            >
              What if?
            </button>
            <button
              onClick={() => {
                useStore.getState().setOverlayTicker(null);
                navigate(`/report/${data.ticker}`);
              }}
              style={{
                padding: "var(--space-xs) var(--space-md)", borderRadius: "var(--radius-sm)",
                background: "var(--color-surface-1)", border: "1px solid var(--color-surface-2)",
                color: "var(--color-text-muted)",
                cursor: "pointer", fontSize: "var(--text-xs)", fontWeight: 600, whiteSpace: "nowrap",
              }}
            >
              Full Report
            </button>
          </div>
        </div>
      </div>

      {/* Price Chart */}
      <InteractiveChart ticker={data.ticker} />

      {/* Hero Verdict Strip — glowing orbit border matches verdict */}
      {data.verdict && (
        <OrbitBorder verdict={data.verdict.recommendation || "WATCHLIST"} radius={18}>
          <HeroVerdictStrip verdict={data.verdict} />
        </OrbitBorder>
      )}

      {/* Position Tile (compact P&L) */}
      {data.position && (
        <CollapsiblePanel
          title="Position"
          preview={
            <span style={{ fontFamily: "var(--font-mono)" }}>
              {data.position.shares.toFixed(2)} shares · {data.position.pnl >= 0 ? "+" : ""}${data.position.pnl.toFixed(2)} ({data.position.pnlPct >= 0 ? "+" : ""}{data.position.pnlPct.toFixed(1)}%)
            </span>
          }
          variant={data.position.pnl >= 0 ? "accent" : "warning"}
          defaultOpen
        >
          <PositionTile position={data.position} />
        </CollapsiblePanel>
      )}

      {/* Signal Pill Badges */}
      {(data.consensusTier || data.stabilityLabel || data.buzz || data.earningsMomentum) && (
        <CollapsiblePanel
          title="Signals"
          preview={
            [
              data.consensusTier && data.consensusTier.replace(/_/g, " "),
              data.stabilityLabel && data.stabilityLabel !== "UNKNOWN" && data.stabilityLabel,
              data.buzz && `Buzz: ${data.buzz.buzzLabel}`,
              data.earningsMomentum && data.earningsMomentum.label.replace(/_/g, " "),
            ].filter(Boolean).join(" · ") || "No signals"
          }
          defaultOpen
        >
          <SignalPills
            consensusTier={data.consensusTier}
            stabilityLabel={data.stabilityLabel}
            stabilityScore={data.stabilityScore}
            buzz={data.buzz}
            earningsMomentum={data.earningsMomentum}
          />
        </CollapsiblePanel>
      )}

      {/* Target Price Range */}
      {data.targetPriceRange && data.targetPriceRange.prices.length >= 2 && f && (
        <CollapsiblePanel
          title="Fair Value Range"
          preview={
            <span style={{ fontFamily: "var(--font-mono)" }}>
              ${data.targetPriceRange.low.toFixed(0)}–${data.targetPriceRange.high.toFixed(0)} · median ${data.targetPriceRange.median.toFixed(0)}
              {f.price < data.targetPriceRange.median
                ? ` (${(((data.targetPriceRange.median - f.price) / f.price) * 100).toFixed(0)}% upside)`
                : ` (${(((f.price - data.targetPriceRange.median) / data.targetPriceRange.median) * 100).toFixed(0)}% above)`
              }
            </span>
          }
          variant="accent"
          defaultOpen
        >
          <div>
            <div style={{ position: "relative", height: 32, marginBottom: "var(--space-sm)" }}>
              {/* Track */}
              <div style={{
                position: "absolute", top: 14, left: 0, right: 0, height: 4,
                background: "var(--color-surface-2)", borderRadius: 2,
              }} />
              {/* Range fill */}
              {(() => {
                const { low, high } = data.targetPriceRange!;
                const padding = (high - low) * 0.15 || high * 0.1;
                const rangeMin = low - padding;
                const rangeMax = high + padding;
                const pct = (v: number) => ((v - rangeMin) / (rangeMax - rangeMin)) * 100;
                return (
                  <>
                    <div style={{
                      position: "absolute", top: 14, height: 4, borderRadius: 2,
                      left: `${pct(low)}%`, width: `${pct(high) - pct(low)}%`,
                      background: "var(--color-accent-bright)", opacity: 0.3,
                    }} />
                    {/* Current price marker */}
                    <div style={{
                      position: "absolute", top: 8, height: 16, width: 2,
                      background: "var(--color-text-primary)",
                      left: `${Math.min(100, Math.max(0, pct(f.price)))}%`,
                    }} />
                    {/* Agent dots */}
                    {data.targetPriceRange!.prices.map((tp, i) => (
                      <div key={i} title={`${tp.agent}: $${tp.price.toFixed(0)}`} style={{
                        position: "absolute", top: 12, width: 8, height: 8,
                        borderRadius: "50%", background: "var(--color-accent-bright)",
                        border: "1px solid var(--color-surface-0)",
                        left: `calc(${pct(tp.price)}% - 4px)`,
                      }} />
                    ))}
                  </>
                );
              })()}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)" }}>
              <span style={{ color: "var(--color-text-muted)" }}>${data.targetPriceRange.low.toFixed(0)}</span>
              <span style={{ color: "var(--color-accent-bright)", fontWeight: 600 }}>median ${data.targetPriceRange.median.toFixed(0)}</span>
              <span style={{ color: "var(--color-text-muted)" }}>${data.targetPriceRange.high.toFixed(0)}</span>
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textAlign: "center", marginTop: 2 }}>
              Current: ${f.price.toFixed(2)}
            </div>
          </div>
        </CollapsiblePanel>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          LAYER 2 — THE WHY (collapsible panels)
         ═══════════════════════════════════════════════════════════════════ */}

      {data.verdict && <AgentAnalysisPanel verdict={data.verdict} signalData={data.signals} />}
      <MetricsPanel profile={p} quantGate={data.quantGate} fundamentals={f} />
      <RiskPanel verdict={data.verdict} competence={data.competence} adversarial={data.verdict?.adversarialResult ?? null} />
      {data.position && (
        <PositionPanel
          position={data.position}
          onSell={() => {
            setShowCloseModal(true);
            setCloseExitPrice((data.position!.currentPrice ?? data.position!.entryPrice).toString());
          }}
        />
      )}
      {data.competence && <CompetencePanel competence={data.competence} />}
      {data.researchBriefing && <ResearchBriefingPanel briefing={data.researchBriefing} />}

      {/* ═══════════════════════════════════════════════════════════════════
          LAYER 3 — THE ARCHIVES (full detail)
         ═══════════════════════════════════════════════════════════════════ */}

      {(data.verdictHistory.length > 1 || data.signals.length > 0 || data.decisions.length > 0 || news.length > 0 || p?.businessSummary || data.watchlist) && (
        <CollapsiblePanel
          title="Archives"
          preview={
            [
              data.verdictHistory.length > 1 && `${data.verdictHistory.length} verdicts`,
              data.signals.length > 0 && `${data.signals.length} signals`,
              data.decisions.length > 0 && `${data.decisions.length} decisions`,
              news.length > 0 && `${news.length} articles`,
            ].filter(Boolean).join(" · ") || "Historical data"
          }
        >
          <ArchiveSection
            verdictHistory={data.verdictHistory}
            signals={data.signals}
            decisions={data.decisions}
            news={news}
            businessSummary={p?.businessSummary ?? null}
            watchlist={data.watchlist}
          />
        </CollapsiblePanel>
      )}

      {/* Empty state */}
      {!data.quantGate && !p && data.signals.length === 0 && data.decisions.length === 0 && !data.verdict && (
        <BentoCard>
          <p style={{ color: "var(--color-text-muted)", textAlign: "center", padding: "var(--space-xl)" }}>
            No analysis data yet. Run the pipeline to analyze this stock.
          </p>
        </BentoCard>
      )}

      {/* Add to Portfolio Modal */}
      {showPortfolioModal && (
        <AddToPortfolioModal
          ticker={data.ticker}
          currentPrice={f?.price ?? 0}
          defaultThesis={data.verdict?.reasoning || ""}
          onClose={() => setShowPortfolioModal(false)}
          onSuccess={(msg) => { setAddStatus(msg); setTimeout(() => setAddStatus(null), 3000); }}
          onError={(msg) => { setAddStatus(msg); setTimeout(() => setAddStatus(null), 3000); }}
        />
      )}

      {/* Scenario Analysis Modal */}
      {showScenarioModal && (
        <ScenarioAnalysis
          ticker={data.ticker}
          currentPrice={f?.price}
          onClose={() => setShowScenarioModal(false)}
          onProceed={() => {
            setShowScenarioModal(false);
            setShowPortfolioModal(true);
          }}
        />
      )}

      {/* Close Position Modal */}
      {showCloseModal && data.position && (
        <div
          onClick={() => setShowCloseModal(false)}
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
              Sell {data.ticker}
            </div>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
              {data.position.shares} shares @ avg ${data.position.entryPrice.toFixed(2)}
            </div>
            <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
              Exit Price
              <input
                type="number"
                step="0.01"
                value={closeExitPrice}
                onChange={(e) => setCloseExitPrice(e.target.value)}
                style={{
                  width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
                  background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
                  borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
                  fontFamily: "var(--font-mono)",
                }}
              />
            </label>
            {(() => {
              const ep = parseFloat(closeExitPrice);
              if (!isNaN(ep) && ep > 0) {
                const pnl = (ep - data.position!.entryPrice) * data.position!.shares;
                const pnlPct = ((ep - data.position!.entryPrice) / data.position!.entryPrice) * 100;
                return (
                  <div style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", color: pnl >= 0 ? "var(--color-success)" : "var(--color-error)" }}>
                    Realized P&L: {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)} ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(1)}%)
                  </div>
                );
              }
              return null;
            })()}
            <div style={{ display: "flex", gap: "var(--space-md)", marginTop: "var(--space-sm)" }}>
              <button
                onClick={() => setShowCloseModal(false)}
                style={{
                  flex: 1, padding: "var(--space-sm) var(--space-md)",
                  background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
                  borderRadius: "var(--radius-sm)", color: "var(--color-text-secondary)", cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleClosePosition}
                style={{
                  flex: 1, padding: "var(--space-sm) var(--space-md)",
                  background: "var(--color-error)", border: "none",
                  borderRadius: "var(--radius-sm)", color: "#fff", cursor: "pointer", fontWeight: 600,
                }}
              >
                Sell Position
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
