import { useState, useEffect, useRef } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { FunnelChart } from "../components/charts/FunnelChart";
import { useQuantGate } from "../hooks/useQuantGate";
import { useAnalysis } from "../contexts/AnalysisContext";
import { useStore } from "../stores/useStore";
import { verdictLabel, verdictBadgeVariant } from "../utils/verdictHelpers";
import type { QuantGateResult } from "../types/models";

function zoneBadge(zone: string | null) {
  if (zone === "safe") return <Badge variant="success">Safe</Badge>;
  if (zone === "grey") return <Badge variant="warning">Grey</Badge>;
  if (zone === "distress") return <Badge variant="error">Distress</Badge>;
  return <Badge variant="neutral">N/A</Badge>;
}

function fScoreBadge(score: number) {
  if (score >= 7) return <Badge variant="success">{score}/9</Badge>;
  if (score >= 4) return <Badge variant="warning">{score}/9</Badge>;
  return <Badge variant="error">{score}/9</Badge>;
}

function compositeBar(score: number | null) {
  if (score == null) return <span style={{ color: "var(--color-text-muted)" }}>—</span>;
  const pct = Math.round(score * 100);
  const color =
    pct >= 70 ? "var(--color-success)" : pct >= 40 ? "var(--color-warning)" : "var(--color-error)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
      <div
        style={{
          width: 48,
          height: 6,
          borderRadius: 3,
          background: "var(--color-surface-2)",
          overflow: "hidden",
        }}
      >
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: color }} />
      </div>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
        {score.toFixed(2)}
      </span>
    </div>
  );
}

function ResultRow({
  result,
  rank,
  onClick,
  onAnalyze,
  isAnalyzing,
}: {
  result: QuantGateResult;
  rank: number;
  onClick: () => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
}) {
  const hasVerdict = result.verdict != null;
  const vLabel = hasVerdict ? verdictLabel[result.verdict!] ?? result.verdict : null;
  const vVariant = hasVerdict ? verdictBadgeVariant[result.verdict!] ?? "neutral" : "neutral";

  return (
    <tr
      onClick={onClick}
      style={{ cursor: "pointer", transition: "background var(--duration-fast) var(--ease-out)" }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.background = "var(--color-surface-1)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.background = "transparent";
      }}
    >
      <Cell align="center">
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
          {rank}
        </span>
      </Cell>
      <Cell>
        <div>
          <span style={{ fontWeight: 600 }}>{result.ticker}</span>
          <div
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
              maxWidth: 160,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {result.name}
          </div>
        </div>
      </Cell>
      <Cell>{compositeBar(result.compositeScore)}</Cell>
      <Cell align="center">{fScoreBadge(result.piotroskiScore)}</Cell>
      <Cell align="center">{zoneBadge(result.altmanZone)}</Cell>
      <Cell align="right">
        <span style={{ fontFamily: "var(--font-mono)" }}>
          {(result.earningsYield * 100).toFixed(1)}%
        </span>
      </Cell>
      <Cell align="center">
        {hasVerdict ? (
          <Badge variant={vVariant}>{vLabel}</Badge>
        ) : (
          <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-xs)" }}>—</span>
        )}
      </Cell>
      <Cell align="center">
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
          {isAnalyzing ? "Running..." : hasVerdict ? "Re-analyze" : "Analyze"}
        </button>
      </Cell>
    </tr>
  );
}

function Cell({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "center" | "right";
}) {
  return (
    <td
      style={{
        textAlign: align,
        padding: "var(--space-sm) var(--space-md)",
        borderBottom: "1px solid var(--glass-border)",
        whiteSpace: "nowrap",
        fontSize: "var(--text-sm)",
      }}
    >
      {children}
    </td>
  );
}

function Th({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "center" | "right";
}) {
  return (
    <th
      style={{
        textAlign: align,
        padding: "var(--space-sm) var(--space-md)",
        color: "var(--color-text-muted)",
        fontWeight: 500,
        fontSize: "var(--text-xs)",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        borderBottom: "1px solid var(--glass-border)",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </th>
  );
}

export function QuantGate() {
  const { latestRun, topResults, loading, error, refetch } = useQuantGate();
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const setScreenerProgress = useStore((s) => s.setScreenerProgress);
  const analysisProgress = useStore((s) => s.analysisProgress);
  const { startAnalysis, isRunning: analysisRunning } = useAnalysis();

  // Track which ticker the analysis is currently on
  const analyzingTicker = analysisRunning ? analysisProgress?.ticker : null;

  // Run Screen on demand
  const [screenRunning, setScreenRunning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const runScreen = async () => {
    if (analysisRunning) return;
    try {
      setScreenRunning(true);
      setScreenerProgress({ stage: "Starting", detail: "Initializing...", pct: 0 });
      const res = await fetch("/api/invest/quant-gate/run", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch("/api/invest/quant-gate/status");
          if (!statusRes.ok) return;
          const status = await statusRes.json();
          const p = status.progress ?? {};
          setScreenerProgress({
            stage: p.stage || "Running",
            detail: p.detail || "",
            pct: p.pct || 0,
          });
          if (!status.running) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setScreenRunning(false);
            if (p.stage === "error") {
              setTimeout(() => setScreenerProgress(null), 5000);
            } else {
              setTimeout(() => setScreenerProgress(null), 3000);
              refetch();
            }
          }
        } catch { /* polling error — continue */ }
      }, 5000);
    } catch (err) {
      console.error("Screen run failed", err);
      setScreenRunning(false);
      setScreenerProgress(null);
    }
  };

  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Quant Gate" />
        <div style={{ padding: "var(--space-xl)" }}>
          <p style={{ color: "var(--color-text-muted)" }}>Loading screener results...</p>
        </div>
      </div>
    );
  }

  if (error || !latestRun) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="Quant Gate" />
        <div style={{ padding: "var(--space-xl)" }}>
          <BentoCard>
            <p style={{ color: "var(--color-error)" }}>
              {error ?? "No screening data available. Run the screener first."}
            </p>
          </BentoCard>
        </div>
      </div>
    );
  }

  // Score distribution for summary
  const safeCount = topResults.filter((r) => r.altmanZone === "safe").length;
  const avgF = topResults.length
    ? (topResults.reduce((s, r) => s + r.piotroskiScore, 0) / topResults.length).toFixed(1)
    : "—";
  const analyzedCount = latestRun.analyzedCount ?? topResults.filter((r) => r.verdict != null).length;

  const funnelStages = [
    { label: "Universe", count: latestRun.stocksScreened },
    { label: "After Exclusions", count: Math.round(latestRun.stocksScreened * 0.7) },
    { label: "Scored", count: Math.round(latestRun.stocksScreened * 0.5) },
    { label: "Top 100", count: latestRun.stocksPassed },
  ];

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Quant Gate"
        subtitle={`Run: ${new Date(latestRun.runDate).toLocaleDateString()}`}
        right={
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
            <button
              onClick={runScreen}
              disabled={screenRunning || analysisRunning}
              style={{
                padding: "var(--space-xs) var(--space-md)",
                fontSize: "var(--text-xs)",
                fontWeight: 600,
                background: screenRunning || analysisRunning ? "var(--color-surface-2)" : "var(--gradient-active)",
                color: screenRunning || analysisRunning ? "var(--color-text-muted)" : "#fff",
                border: "none",
                borderRadius: "var(--radius-full)",
                cursor: screenRunning || analysisRunning ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {screenRunning ? "Screening..." : "Run Screen"}
            </button>
            <Badge variant="accent">
              {latestRun.stocksPassed} passed
            </Badge>
          </div>
        }
      />

      <div
        style={{
          padding: "var(--space-lg)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-lg)",
        }}
      >
        {/* Summary Metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr", gap: "var(--space-md)" }}>
          <BentoCard title="Screened">
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
              {latestRun.stocksScreened.toLocaleString()}
            </div>
          </BentoCard>
          <BentoCard title="Passed">
            <div
              style={{
                fontSize: "var(--text-xl)",
                fontWeight: 700,
                fontFamily: "var(--font-mono)",
                color: "var(--color-success)",
              }}
            >
              {latestRun.stocksPassed}
            </div>
          </BentoCard>
          <BentoCard title="Analyzed">
            <div
              style={{
                fontSize: "var(--text-xl)",
                fontWeight: 700,
                fontFamily: "var(--font-mono)",
                color: "var(--color-accent-bright)",
              }}
            >
              {analyzedCount}
            </div>
          </BentoCard>
          <BentoCard title="Avg F-Score">
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
              {avgF}
            </div>
          </BentoCard>
          <BentoCard title="Z-Safe">
            <div
              style={{
                fontSize: "var(--text-xl)",
                fontWeight: 700,
                fontFamily: "var(--font-mono)",
                color: "var(--color-success)",
              }}
            >
              {safeCount}
              <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
                /{topResults.length}
              </span>
            </div>
          </BentoCard>
        </div>

        {/* Funnel */}
        <BentoCard title="Screening Funnel">
          <FunnelChart stages={funnelStages} />
        </BentoCard>

        {/* Results Table */}
        <BentoCard title="Top Results — Sorted by Composite Score">
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <Th align="center">#</Th>
                  <Th>Stock</Th>
                  <Th>Composite</Th>
                  <Th align="center">F-Score</Th>
                  <Th align="center">Z-Zone</Th>
                  <Th align="right">EY</Th>
                  <Th align="center">Verdict</Th>
                  <Th align="center">Action</Th>
                </tr>
              </thead>
              <tbody>
                {topResults.map((r, i) => (
                  <ResultRow
                    key={r.ticker}
                    result={r}
                    rank={i + 1}
                    onClick={() => setOverlayTicker(r.ticker)}
                    onAnalyze={() => { if (!analysisRunning) startAnalysis([r.ticker]); }}
                    isAnalyzing={analyzingTicker === r.ticker}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </BentoCard>

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}
