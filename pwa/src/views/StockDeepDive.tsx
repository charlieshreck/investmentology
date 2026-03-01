import { useEffect, useState, useCallback, useRef } from "react";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { AddToPortfolioModal } from "../components/shared/AddToPortfolioModal";
import { PriceChart } from "../components/charts/PriceChart";
import { MarketStatus } from "../components/shared/MarketStatus";
import { verdictColor, verdictLabel, verdictBadgeVariant } from "../utils/verdictHelpers";
import { useAnalysis } from "../contexts/AnalysisContext";
import { useStore } from "../stores/useStore";

interface Fundamentals {
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

interface QuantGate {
  combinedRank: number;
  eyRank: number;
  roicRank: number;
  piotroskiScore: number;
  altmanZScore: number | null;
  altmanZone: string | null;
  compositeScore: number | null;
}

interface Profile {
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

interface Signal {
  agentName: string;
  model: string;
  signals: Record<string, unknown>;
  confidence: number | null;
  reasoning: string;
  createdAt: string;
}

interface Decision {
  id: string;
  decisionType: string;
  layer: string;
  confidence: number | null;
  reasoning: string;
  createdAt: string;
}

interface AgentStance {
  name: string;
  sentiment: number;
  confidence: number;
  key_signals: string[];
  summary: string;
}

interface VerdictData {
  recommendation: string;
  confidence: number | null;
  consensusScore: number | null;
  reasoning: string;
  agentStances: AgentStance[] | null;
  riskFlags: string[] | null;
  auditorOverride: boolean;
  mungerOverride: boolean;
  createdAt: string | null;
}

interface MoatData {
  type: string;
  sources: string[];
  trajectory: string;
  durability_years: number;
  confidence: number;
  reasoning: string;
}

interface CompetenceData {
  passed: boolean;
  confidence: number | null;
  reasoning: string;
  in_circle?: boolean;
  sector_familiarity?: string;
  moat?: MoatData | null;
}

interface WatchlistInfo {
  state: string;
  notes: string | null;
  updated_at: string | null;
}

interface NewsArticle {
  title: string;
  summary: string;
  publisher: string;
  url: string;
  published_at: string | null;
  type: string;
}

interface BuzzData {
  buzzScore: number;
  buzzLabel: string;
  headlineSentiment: number | null;
  articleCount: number;
  contrarianFlag: boolean;
}

interface EarningsMomentum {
  score: number;
  label: string;
  upwardRevisions: number;
  downwardRevisions: number;
  beatStreak: number;
}

interface PositionData {
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

interface BriefingData {
  headline: string;
  situation: string;
  action: string;
  rationale: string;
}

interface StockResponse {
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
}

function formatCap(cap: number): string {
  if (!cap) return "—";
  if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`;
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`;
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(0)}M`;
  return `$${cap.toLocaleString()}`;
}

function formatNum(n: number): string {
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function formatVol(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toLocaleString();
}

function sentimentBar(sentiment: number) {
  const pct = Math.round((sentiment + 1) * 50);
  const color = sentiment > 0.1 ? "var(--color-success)" : sentiment < -0.1 ? "var(--color-error)" : "var(--color-warning)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", minWidth: 80 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 2, background: "var(--color-surface-2)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 2, background: color }} />
      </div>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color }}>
        {sentiment > 0 ? "+" : ""}{sentiment.toFixed(2)}
      </span>
    </div>
  );
}

function VerdictCard({ verdict }: { verdict: VerdictData }) {
  const color = verdictColor[verdict.recommendation] ?? "var(--color-text-muted)";
  const label = verdictLabel[verdict.recommendation] ?? verdict.recommendation;
  const variant = verdictBadgeVariant[verdict.recommendation] ?? "neutral";

  return (
    <div style={{ background: "var(--color-surface-1)", border: `2px solid ${color}`, borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
      <div style={{ padding: "var(--space-lg)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
          <span style={{ fontSize: "var(--text-2xl)", fontWeight: 800, color, fontFamily: "var(--font-mono)", letterSpacing: "0.02em" }}>{label}</span>
          {verdict.auditorOverride && <Badge variant="error">Auditor Override</Badge>}
          {verdict.mungerOverride && <Badge variant="error">Munger Veto</Badge>}
        </div>
        <div style={{ textAlign: "right" }}>
          {verdict.confidence != null && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "var(--space-xs)" }}>
              <Badge variant={variant}>{(verdict.confidence * 100).toFixed(0)}% confidence</Badge>
              {verdict.consensusScore != null && (
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                  consensus: {verdict.consensusScore > 0 ? "+" : ""}{verdict.consensusScore.toFixed(3)}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
      <div style={{ padding: "0 var(--space-lg) var(--space-lg)", fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6, borderTop: "1px solid var(--glass-border)", paddingTop: "var(--space-md)" }}>
        {verdict.reasoning}
      </div>
      {verdict.agentStances && verdict.agentStances.length > 0 && (
        <div style={{ padding: "0 var(--space-lg) var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Agent Consensus</div>
          {verdict.agentStances.map((s) => (
            <div key={s.name} style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", padding: "var(--space-sm) var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
              <span style={{ fontWeight: 600, fontSize: "var(--text-sm)", minWidth: 64 }}>{s.name.charAt(0).toUpperCase() + s.name.slice(1)}</span>
              {sentimentBar(s.sentiment)}
              <Badge variant={s.confidence >= 0.7 ? "success" : s.confidence >= 0.4 ? "warning" : "error"}>{(s.confidence * 100).toFixed(0)}%</Badge>
            </div>
          ))}
        </div>
      )}
      {verdict.riskFlags && verdict.riskFlags.length > 0 && (
        <div style={{ padding: "0 var(--space-lg) var(--space-lg)" }}>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-error)", fontWeight: 600, marginBottom: "var(--space-xs)" }}>Risk Flags</div>
          {verdict.riskFlags.map((flag, i) => (
            <div key={i} style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", paddingLeft: "var(--space-md)", borderLeft: "2px solid var(--color-error)", marginBottom: "var(--space-xs)" }}>{flag}</div>
          ))}
        </div>
      )}
      {verdict.createdAt && (
        <div style={{ padding: "0 var(--space-lg) var(--space-md)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textAlign: "right" }}>
          Computed {new Date(verdict.createdAt).toLocaleString()}
        </div>
      )}
    </div>
  );
}

function zoneBadge(zone: string | null) {
  if (zone === "safe") return <Badge variant="success">Safe</Badge>;
  if (zone === "grey") return <Badge variant="warning">Grey</Badge>;
  if (zone === "distress") return <Badge variant="error">Distress</Badge>;
  return <Badge variant="neutral">N/A</Badge>;
}

function stateBadge(state: string) {
  const map: Record<string, "accent" | "success" | "warning" | "error" | "neutral"> = {
    CANDIDATE: "accent", CONVICTION_BUY: "success", POSITION_HOLD: "success",
    WATCHLIST_EARLY: "accent", WATCHLIST_CATALYST: "warning",
    REJECTED: "error", POSITION_SELL: "warning",
  };
  return <Badge variant={map[state] ?? "neutral"}>{state.replace(/_/g, " ")}</Badge>;
}

function Metric({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>{label}</div>
      <div style={{ fontWeight: 600, fontFamily: mono ? "var(--font-mono)" : "inherit" }}>{value}</div>
    </div>
  );
}

function recBadge(rec: string) {
  const map: Record<string, "success" | "warning" | "error" | "neutral"> = {
    "strong_buy": "success", "buy": "success", "hold": "warning",
    "sell": "error", "strong_sell": "error", "underperform": "error",
  };
  return <Badge variant={map[rec] ?? "neutral"}>{rec.replace(/_/g, " ").toUpperCase()}</Badge>;
}

function FiftyTwoWeekBar({ low, high, current }: { low: number; high: number; current: number }) {
  const range = high - low;
  const pct = range > 0 ? Math.max(0, Math.min(100, ((current - low) / range) * 100)) : 50;
  return (
    <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-sm)" }}>52-Week Range</div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
        <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-error)" }}>${low.toFixed(0)}</span>
        <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--color-surface-2)", position: "relative" }}>
          <div style={{ position: "absolute", left: `${pct}%`, top: -2, width: 10, height: 10, borderRadius: "50%", background: "var(--color-accent-bright)", transform: "translateX(-50%)" }} />
        </div>
        <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-success)" }}>${high.toFixed(0)}</span>
      </div>
    </div>
  );
}

function SignalRow({ signal }: { signal: Signal }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{ background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex", alignItems: "center", gap: "var(--space-md)",
          padding: "var(--space-sm) var(--space-md)", cursor: "pointer",
        }}
      >
        <span style={{ fontWeight: 600, fontSize: "var(--text-sm)", minWidth: 64 }}>
          {signal.agentName.charAt(0).toUpperCase() + signal.agentName.slice(1)}
        </span>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", minWidth: 60 }}>{signal.model}</span>
        <div style={{ flex: 1 }} />
        {signal.confidence != null && (
          <Badge variant={signal.confidence >= 0.7 ? "success" : signal.confidence >= 0.4 ? "warning" : "error"}>
            {(signal.confidence * 100).toFixed(0)}%
          </Badge>
        )}
        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>
          ▼
        </span>
      </div>
      {expanded && (
        <div style={{ padding: "0 var(--space-md) var(--space-md)", fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6, borderTop: "1px solid var(--glass-border)" }}>
          {signal.reasoning}
        </div>
      )}
    </div>
  );
}

export function StockDeepDive({ ticker }: { ticker: string }) {
  const [data, setData] = useState<StockResponse | null>(null);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addStatus, setAddStatus] = useState<string | null>(null);
  const [showPortfolioModal, setShowPortfolioModal] = useState(false);
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [closeExitPrice, setCloseExitPrice] = useState("");
  const [refetchKey, setRefetchKey] = useState(0);

  const refetchStock = useCallback(() => {
    setRefetchKey((k) => k + 1);
  }, []);

  const { startAnalysis, isRunning: analysisRunning } = useAnalysis();
  const analysisProgress = useStore((s) => s.analysisProgress);
  const isAnalyzing = analysisRunning && analysisProgress?.ticker === ticker;

  // Refetch when analysis for this ticker completes
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

  if (loading) return (
    <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
      <div className="skeleton" style={{ height: 24, width: "40%" }} />
      <div className="skeleton" style={{ height: 200 }} />
      <div className="skeleton" style={{ height: 16, width: "80%" }} />
      <div className="skeleton" style={{ height: 16, width: "60%" }} />
    </div>
  );
  if (error || !data) return <BentoCard><p style={{ color: "var(--color-error)" }}>Failed to load {ticker}: {error ?? "No data"}</p></BentoCard>;

  const f = data.fundamentals;
  const q = data.quantGate;
  const p = data.profile;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
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
                padding: "var(--space-xs) var(--space-md)",
                borderRadius: "var(--radius-sm)",
                background: isAnalyzing ? "var(--color-surface-2)" : "var(--color-accent-ghost)",
                border: "none",
                color: isAnalyzing ? "var(--color-text-muted)" : "var(--color-accent-bright)",
                cursor: isAnalyzing ? "wait" : "pointer",
                fontSize: "var(--text-xs)",
                fontWeight: 600,
                whiteSpace: "nowrap",
              }}
            >
              {isAnalyzing ? "Analyzing..." : "Analyze"}
            </button>
            {f && (
              <button
                onClick={() => setShowPortfolioModal(true)}
                style={{
                  padding: "var(--space-xs) var(--space-md)",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--gradient-active)",
                  border: "none",
                  color: "#fff",
                  cursor: "pointer",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                }}
              >
                + Portfolio
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Price Chart */}
      <PriceChart ticker={data.ticker} />

      {/* Briefing */}
      {data.briefing && (
        <BentoCard title="Advisory Briefing">
          <div style={{ fontWeight: 700, fontSize: "var(--text-base)", color: "var(--color-accent-bright)", marginBottom: "var(--space-md)", lineHeight: 1.4 }}>
            {data.briefing.headline}
          </div>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.7, marginBottom: "var(--space-md)" }}>
            {data.briefing.situation}
          </div>
          <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)", borderLeft: "3px solid var(--color-accent)", marginBottom: "var(--space-md)" }}>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-xs)" }}>Action</div>
            <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, lineHeight: 1.6 }}>{data.briefing.action}</div>
          </div>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.7 }}>
            {data.briefing.rationale}
          </div>
        </BentoCard>
      )}

      {/* Position */}
      {data.position && (
        <BentoCard title="Your Position">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "var(--space-md)" }}>
            <Metric label="Shares" value={data.position.shares.toFixed(2)} mono />
            <Metric label="Entry" value={`$${data.position.entryPrice.toFixed(2)}`} mono />
            <Metric label="Current" value={`$${data.position.currentPrice.toFixed(2)}`} mono />
            <Metric label="P&L" value={
              <span style={{ color: data.position.pnl >= 0 ? "var(--color-success)" : "var(--color-error)" }}>
                {data.position.pnl >= 0 ? "+" : ""}${data.position.pnl.toFixed(2)} ({data.position.pnlPct >= 0 ? "+" : ""}{data.position.pnlPct.toFixed(1)}%)
              </span>
            } />
            {data.position.weight != null && <Metric label="Weight" value={`${(data.position.weight * 100).toFixed(1)}%`} mono />}
            {data.position.entryDate && <Metric label="Held" value={`${Math.floor((Date.now() - new Date(data.position.entryDate).getTime()) / 86400000)}d`} mono />}
            {data.position.stopLoss != null && <Metric label="Stop Loss" value={`$${data.position.stopLoss.toFixed(2)}`} mono />}
            {data.position.fairValue != null && <Metric label="Fair Value" value={`$${data.position.fairValue.toFixed(2)}`} mono />}
          </div>
          <div style={{ marginTop: "var(--space-md)", display: "flex", gap: "var(--space-sm)" }}>
            {data.position.positionType && (
              <Badge variant={data.position.positionType === "core" ? "success" : data.position.positionType === "speculative" ? "warning" : "accent"}>
                {data.position.positionType}
              </Badge>
            )}
            <button
              onClick={() => { setShowCloseModal(true); setCloseExitPrice(data.position!.currentPrice.toString()); }}
              style={{
                marginLeft: "auto",
                padding: "var(--space-xs) var(--space-md)",
                borderRadius: "var(--radius-sm)",
                background: "var(--color-error)",
                border: "none",
                color: "#fff",
                cursor: "pointer",
                fontSize: "var(--text-xs)",
                fontWeight: 600,
              }}
            >
              Sell
            </button>
          </div>
          {data.position.thesis && (
            <div style={{ marginTop: "var(--space-md)", fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6, fontStyle: "italic", borderTop: "1px solid var(--glass-border)", paddingTop: "var(--space-md)" }}>
              {data.position.thesis}
            </div>
          )}
        </BentoCard>
      )}

      {/* Business Summary */}
      {p?.businessSummary && (
        <BentoCard title="Business">
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.7 }}>
            {p.businessSummary}
          </div>
        </BentoCard>
      )}

      {/* Competence Assessment */}
      {data.competence && (
        <BentoCard title="Competence Assessment">
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", marginBottom: "var(--space-md)", flexWrap: "wrap" }}>
            <Badge variant={data.competence.passed ? "success" : "warning"}>
              {data.competence.passed ? "In Circle" : "Outside Circle"}
            </Badge>
            {data.competence.confidence != null && (
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>
                {(data.competence.confidence * 100).toFixed(0)}% confidence
              </span>
            )}
            {data.competence.sector_familiarity && (
              <Badge variant={data.competence.sector_familiarity === "high" ? "success" : data.competence.sector_familiarity === "medium" ? "warning" : "error"}>
                {data.competence.sector_familiarity} familiarity
              </Badge>
            )}
          </div>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
            {data.competence.reasoning}
          </div>
          {data.competence.moat && (
            <div style={{ marginTop: "var(--space-md)", paddingTop: "var(--space-md)", borderTop: "1px solid var(--glass-border)" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-sm)" }}>
                Moat Analysis
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)", marginBottom: "var(--space-sm)" }}>
                <Metric label="Moat Type" value={data.competence.moat.type || "none"} />
                <Metric label="Trajectory" value={data.competence.moat.trajectory || "—"} />
                <Metric label="Durability" value={`${data.competence.moat.durability_years}y`} mono />
              </div>
              {data.competence.moat.sources?.length > 0 && (
                <div style={{ display: "flex", gap: "var(--space-xs)", flexWrap: "wrap", marginBottom: "var(--space-sm)" }}>
                  {data.competence.moat.sources.map((s: string) => <Badge key={s} variant="accent">{s.replace(/_/g, " ")}</Badge>)}
                </div>
              )}
              <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>{data.competence.moat.reasoning}</div>
            </div>
          )}
        </BentoCard>
      )}

      {/* Verdict */}
      {data.verdict && <VerdictCard verdict={data.verdict} />}

      {/* Signal Intelligence */}
      {(data.buzz || data.earningsMomentum || data.stabilityLabel || data.consensusTier) && (
        <BentoCard title="Signal Intelligence">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "var(--space-md)" }}>
            {data.consensusTier && (
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)", borderLeft: `3px solid ${data.consensusTier === "HIGH_CONVICTION" ? "var(--color-success)" : data.consensusTier === "CONTRARIAN" ? "#a78bfa" : "var(--color-warning)"}` }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Consensus Tier</div>
                <div style={{ fontWeight: 700, fontSize: "var(--text-sm)", color: data.consensusTier === "HIGH_CONVICTION" ? "var(--color-success)" : data.consensusTier === "CONTRARIAN" ? "#a78bfa" : "var(--color-warning)" }}>
                  {data.consensusTier.replace(/_/g, " ")}
                </div>
              </div>
            )}
            {data.stabilityLabel && data.stabilityLabel !== "UNKNOWN" && (
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)", borderLeft: `3px solid ${data.stabilityLabel === "STABLE" ? "var(--color-success)" : data.stabilityLabel === "UNSTABLE" ? "var(--color-error)" : "var(--color-warning)"}` }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Verdict Stability</div>
                <div style={{ fontWeight: 700, fontSize: "var(--text-sm)" }}>{data.stabilityLabel}</div>
                {data.stabilityScore != null && (
                  <div style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>{(data.stabilityScore * 100).toFixed(0)}%</div>
                )}
              </div>
            )}
            {data.buzz && (
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)", borderLeft: `3px solid ${data.buzz.buzzLabel === "HIGH" ? "var(--color-error)" : data.buzz.buzzLabel === "MODERATE" ? "var(--color-warning)" : "var(--color-success)"}` }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Media Buzz</div>
                <div style={{ fontWeight: 700, fontSize: "var(--text-sm)" }}>{data.buzz.buzzLabel}</div>
                <div style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
                  {data.buzz.buzzScore}/100 ({data.buzz.articleCount} articles)
                </div>
                {data.buzz.headlineSentiment != null && (
                  <div style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: data.buzz.headlineSentiment > 0 ? "var(--color-success)" : data.buzz.headlineSentiment < 0 ? "var(--color-error)" : "var(--color-text-muted)" }}>
                    sentiment: {data.buzz.headlineSentiment > 0 ? "+" : ""}{data.buzz.headlineSentiment.toFixed(2)}
                  </div>
                )}
                {data.buzz.contrarianFlag && (
                  <Badge variant="accent">Contrarian</Badge>
                )}
              </div>
            )}
            {data.earningsMomentum && (
              <div style={{ padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)", borderLeft: `3px solid ${data.earningsMomentum.label === "STRONG_UP" || data.earningsMomentum.label === "UP" ? "var(--color-success)" : data.earningsMomentum.label === "DOWN" || data.earningsMomentum.label === "STRONG_DOWN" ? "var(--color-error)" : "var(--color-text-muted)"}` }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Earnings Momentum</div>
                <div style={{ fontWeight: 700, fontSize: "var(--text-sm)" }}>{data.earningsMomentum.label.replace(/_/g, " ")}</div>
                <div style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
                  {data.earningsMomentum.upwardRevisions > 0 && <span style={{ color: "var(--color-success)" }}>{data.earningsMomentum.upwardRevisions} up</span>}
                  {data.earningsMomentum.upwardRevisions > 0 && data.earningsMomentum.downwardRevisions > 0 && " / "}
                  {data.earningsMomentum.downwardRevisions > 0 && <span style={{ color: "var(--color-error)" }}>{data.earningsMomentum.downwardRevisions} down</span>}
                </div>
                {data.earningsMomentum.beatStreak > 0 && (
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-success)" }}>{data.earningsMomentum.beatStreak}Q beat streak</div>
                )}
              </div>
            )}
          </div>
        </BentoCard>
      )}

      {/* Verdict History Timeline */}
      {data.verdictHistory && data.verdictHistory.length > 1 && (
        <BentoCard title="Verdict History">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
            {data.verdictHistory.map((v, i) => {
              const vColor = verdictColor[v.recommendation] ?? "var(--color-text-muted)";
              const vLbl = verdictLabel[v.recommendation] ?? v.recommendation;
              const vVariant = verdictBadgeVariant[v.recommendation] ?? "neutral";
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", padding: "var(--space-sm) var(--space-md)", borderLeft: i === 0 ? `3px solid ${vColor}` : "3px solid var(--glass-border)", background: i === 0 ? "var(--color-surface-1)" : "transparent", borderRadius: "0 var(--radius-sm) var(--radius-sm) 0" }}>
                  <Badge variant={vVariant}>{vLbl}</Badge>
                  {v.confidence != null && <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>{(v.confidence * 100).toFixed(0)}%</span>}
                  {v.consensusScore != null && <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>cs:{v.consensusScore > 0 ? "+" : ""}{v.consensusScore.toFixed(2)}</span>}
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginLeft: "auto" }}>{v.createdAt ? new Date(v.createdAt).toLocaleDateString() : ""}</span>
                </div>
              );
            })}
          </div>
        </BentoCard>
      )}

      {/* Valuation & Market Metrics */}
      {(p || q) && (
        <BentoCard title="Key Metrics">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "var(--space-md)" }}>
            {p?.trailingPE != null && <Metric label="P/E (TTM)" value={p.trailingPE.toFixed(1)} mono />}
            {p?.forwardPE != null && <Metric label="P/E (Fwd)" value={p.forwardPE.toFixed(1)} mono />}
            {p?.priceToBook != null && <Metric label="P/B" value={p.priceToBook.toFixed(2)} mono />}
            {p?.priceToSales != null && <Metric label="P/S" value={p.priceToSales.toFixed(2)} mono />}
            {f?.earnings_yield != null && <Metric label="Earnings Yield" value={`${(f.earnings_yield * 100).toFixed(1)}%`} mono />}
            {f?.roic != null && <Metric label="ROIC" value={`${(f.roic * 100).toFixed(0)}%`} mono />}
            {p?.beta != null && <Metric label="Beta" value={p.beta.toFixed(2)} mono />}
            {p?.dividendYield != null && <Metric label="Div Yield" value={`${p.dividendYield.toFixed(2)}%`} mono />}
            {p?.averageVolume != null && <Metric label="Avg Volume" value={formatVol(p.averageVolume)} mono />}
          </div>
          {p?.fiftyTwoWeekLow != null && p?.fiftyTwoWeekHigh != null && f && (
            <div style={{ marginTop: "var(--space-md)" }}>
              <FiftyTwoWeekBar low={p.fiftyTwoWeekLow} high={p.fiftyTwoWeekHigh} current={f.price} />
            </div>
          )}
          {/* Analyst consensus */}
          {p?.analystRecommendation && (
            <div style={{ marginTop: "var(--space-md)", display: "flex", alignItems: "center", gap: "var(--space-md)", padding: "var(--space-md)", background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)" }}>
              <div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Analyst Consensus</div>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
                  {recBadge(p.analystRecommendation)}
                  {p.analystCount != null && <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>({p.analystCount} analysts)</span>}
                </div>
              </div>
              {p.analystTarget != null && f && (
                <div style={{ marginLeft: "auto", textAlign: "right" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>Target</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>${p.analystTarget.toFixed(0)}</div>
                  <div style={{
                    fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)",
                    color: p.analystTarget > f.price ? "var(--color-success)" : "var(--color-error)",
                  }}>
                    {p.analystTarget > f.price ? "+" : ""}{(((p.analystTarget - f.price) / f.price) * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
          )}
        </BentoCard>
      )}

      {/* Quant Gate Scoring */}
      {q && (
        <BentoCard title="Quant Gate Scoring">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)", marginBottom: "var(--space-lg)" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Composite</div>
              <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700, fontFamily: "var(--font-mono)", color: (q.compositeScore ?? 0) >= 0.7 ? "var(--color-success)" : (q.compositeScore ?? 0) >= 0.4 ? "var(--color-warning)" : "var(--color-error)" }}>
                {q.compositeScore?.toFixed(2) ?? "—"}
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Piotroski F</div>
              <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{q.piotroskiScore}<span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>/9</span></div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Altman Z</div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-xs)" }}>
                <span style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{q.altmanZScore?.toFixed(1) ?? "—"}</span>
                {zoneBadge(q.altmanZone)}
              </div>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)" }}>
            <Metric label="Greenblatt Rank" value={`#${q.combinedRank}`} mono />
            <Metric label="EY Rank" value={`#${q.eyRank}`} mono />
            <Metric label="ROIC Rank" value={`#${q.roicRank}`} mono />
          </div>
        </BentoCard>
      )}

      {/* Fundamentals */}
      {f && (
        <BentoCard title="Fundamentals">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)" }}>
            <Metric label="Market Cap" value={formatCap(f.market_cap)} mono />
            <Metric label="EV" value={formatCap(f.enterprise_value)} mono />
            <Metric label="EY" value={f.earnings_yield ? `${(f.earnings_yield * 100).toFixed(1)}%` : "—"} mono />
            <Metric label="Revenue" value={formatNum(f.revenue)} mono />
            <Metric label="Net Income" value={formatNum(f.net_income)} mono />
            <Metric label="Op Income" value={formatNum(f.operating_income)} mono />
            <Metric label="Cash" value={formatNum(f.cash)} mono />
            <Metric label="Debt" value={formatNum(f.total_debt)} mono />
            <Metric label="Shares" value={`${(f.shares_outstanding / 1e6).toFixed(1)}M`} mono />
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-md)", textAlign: "right" }}>
            Data as of {new Date(f.fetched_at).toLocaleDateString()}
          </div>
        </BentoCard>
      )}

      {/* Agent Signals */}
      {data.signals.length > 0 && (
        <BentoCard title="Agent Signals">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {data.signals.map((s, i) => (
              <SignalRow key={i} signal={s} />
            ))}
          </div>
        </BentoCard>
      )}

      {/* News */}
      {news.length > 0 && (
        <BentoCard title="Recent News">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {news.map((article, i) => (
              <a
                key={i}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "block", padding: "var(--space-md)", borderRadius: "var(--radius-sm)", background: "var(--color-surface-0)",
                  textDecoration: "none", color: "inherit", transition: "background var(--duration-fast) var(--ease-out)",
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-1)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-0)"; }}
              >
                <div style={{ fontWeight: 600, fontSize: "var(--text-sm)", marginBottom: "var(--space-xs)", color: "var(--color-text-primary)" }}>
                  {article.title}
                </div>
                {article.summary && (
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.5, marginBottom: "var(--space-xs)" }}>
                    {article.summary.length > 160 ? article.summary.slice(0, 160) + "..." : article.summary}
                  </div>
                )}
                <div style={{ display: "flex", gap: "var(--space-md)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {article.publisher && <span>{article.publisher}</span>}
                  {article.published_at && <span>{new Date(article.published_at).toLocaleDateString()}</span>}
                </div>
              </a>
            ))}
          </div>
        </BentoCard>
      )}

      {/* Decisions */}
      {data.decisions.length > 0 && (
        <BentoCard title="Decision History">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {data.decisions.map((d) => (
              <div key={d.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)" }}>
                <div>
                  <Badge variant="neutral">{d.decisionType}</Badge>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginLeft: "var(--space-md)" }}>{d.layer} — {d.createdAt ? new Date(d.createdAt).toLocaleDateString() : ""}</span>
                </div>
                {d.confidence != null && <Badge variant={d.confidence >= 0.7 ? "success" : d.confidence >= 0.4 ? "warning" : "error"}>{(d.confidence * 100).toFixed(0)}%</Badge>}
              </div>
            ))}
          </div>
        </BentoCard>
      )}

      {/* Watchlist Info */}
      {data.watchlist && (
        <BentoCard title="Watchlist">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              {stateBadge(data.watchlist.state)}
              {data.watchlist.notes && <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginLeft: "var(--space-md)" }}>{data.watchlist.notes}</span>}
            </div>
            {data.watchlist.updated_at && <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>{new Date(data.watchlist.updated_at).toLocaleDateString()}</span>}
          </div>
        </BentoCard>
      )}

      {/* Empty state */}
      {!q && !p && data.signals.length === 0 && data.decisions.length === 0 && (
        <BentoCard>
          <p style={{ color: "var(--color-text-muted)", textAlign: "center", padding: "var(--space-xl)" }}>
            No analysis data yet. Run the pipeline to analyze this stock.
          </p>
        </BentoCard>
      )}

      {/* Add to Portfolio Modal */}
      {showPortfolioModal && f && (
        <AddToPortfolioModal
          ticker={data.ticker}
          currentPrice={f.price}
          defaultThesis={data.verdict?.reasoning || ""}
          onClose={() => setShowPortfolioModal(false)}
          onSuccess={(msg) => { setAddStatus(msg); setTimeout(() => setAddStatus(null), 3000); }}
          onError={(msg) => { setAddStatus(msg); setTimeout(() => setAddStatus(null), 3000); }}
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
