import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { Skeleton } from "../components/shared/Skeleton";
import {
  usePipelineStatus,
  usePipelineTickers,
  usePipelineTickerDetail,
  usePipelineFunnel,
  usePipelineHealth,
} from "../hooks/usePipeline";
import { PRE_FILTER_EXPLANATIONS, SCREENER_NAMES } from "../utils/glossary";
import type {
  PipelineTickerSummary,
  PipelineStepDetail,
  PipelineScreenerVerdict,
  PipelineFunnel,
  PipelineHealth,
} from "../types/models";

function formatStepName(step: string): string {
  if (step.startsWith("agent:")) {
    const name = step.slice(6);
    return name.charAt(0).toUpperCase() + name.slice(1);
  }
  if (step.startsWith("screener:")) {
    const key = step.slice(9);
    return SCREENER_NAMES[key]?.label ?? key.replace(/_/g, " ");
  }
  const labels: Record<string, string> = {
    data_fetch: "Data Collection",
    data_validate: "Data Validation",
    pre_filter: "Quick Health Check",
    gate_decision: "Screening Decision",
    debate: "Debate",
    synthesis: "Final Verdict",
  };
  return labels[step] ?? step.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function getStepPhase(step: string): "screening" | "analysis" {
  if (
    step === "data_fetch" ||
    step === "data_validate" ||
    step === "pre_filter" ||
    step.startsWith("screener:") ||
    step === "gate_decision"
  ) {
    return "screening";
  }
  return "analysis";
}

const stepStatusColors: Record<string, string> = {
  pending: "var(--color-surface-3)",
  running: "var(--color-accent)",
  completed: "var(--color-success)",
  failed: "var(--color-error)",
  expired: "var(--color-warning)",
};

// ---------------------------------------------------------------------------
// Shared micro-components
// ---------------------------------------------------------------------------

function StepDot({ status }: { status: string }) {
  const color = stepStatusColors[status] ?? "var(--color-surface-3)";
  const isRunning = status === "running";
  return (
    <motion.div
      animate={
        isRunning
          ? { scale: [1, 1.4, 1], opacity: [1, 0.7, 1] }
          : { scale: 1 }
      }
      transition={
        isRunning
          ? { repeat: Infinity, duration: 1.5, ease: "easeInOut" }
          : { type: "spring", stiffness: 400, damping: 25 }
      }
      style={{
        width: 8,
        height: 8,
        borderRadius: "var(--radius-full)",
        background: color,
        boxShadow: isRunning ? `0 0 8px ${color}` : "none",
        flexShrink: 0,
      }}
    />
  );
}

function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <span
      style={{ position: "relative", cursor: "help" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onClick={() => setShow((v) => !v)}
    >
      {children}
      {show && (
        <span
          style={{
            position: "absolute",
            bottom: "calc(100% + 6px)",
            left: "50%",
            transform: "translateX(-50%)",
            padding: "6px 10px",
            background: "var(--color-surface-1)",
            border: "1px solid var(--glass-border)",
            borderRadius: "var(--radius-sm)",
            fontSize: 11,
            color: "var(--color-text-secondary)",
            whiteSpace: "nowrap",
            maxWidth: 260,
            zIndex: 50,
            boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
            lineHeight: 1.4,
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Funnel visualization
// ---------------------------------------------------------------------------

function FunnelBar({
  label,
  count,
  maxCount,
  color,
  detail,
  tooltip,
}: {
  label: string;
  count: number;
  maxCount: number;
  color: string;
  detail?: string;
  tooltip?: string;
}) {
  const pct = maxCount > 0 ? Math.max((count / maxCount) * 100, 4) : 0;
  const bar = (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "var(--text-xs)", fontWeight: 500, color: "var(--color-text-secondary)" }}>
          {label}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 700, color }}>
          {count}
        </span>
      </div>
      <div style={{
        height: 6,
        background: "var(--color-surface-2)",
        borderRadius: "var(--radius-full)",
        overflow: "hidden",
      }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          style={{ height: "100%", background: color, borderRadius: "var(--radius-full)" }}
        />
      </div>
      {detail && (
        <span style={{ fontSize: 10, color: "var(--color-text-muted)", lineHeight: 1.3 }}>
          {detail}
        </span>
      )}
    </div>
  );

  if (tooltip) {
    return <Tooltip text={tooltip}>{bar}</Tooltip>;
  }
  return bar;
}

function FunnelView({ funnel }: { funnel: PipelineFunnel }) {
  if (!funnel.hasCycle || !funnel.stages) {
    return (
      <BentoCard variant="accent">
        <div style={{
          textAlign: "center",
          padding: "var(--space-xl) 0",
          color: "var(--color-text-muted)",
          fontSize: "var(--text-sm)",
        }}>
          No active pipeline cycle. The system starts automatically when new stocks are ready to evaluate.
        </div>
      </BentoCard>
    );
  }

  const s = funnel.stages;
  const total = funnel.totalTickers ?? 0;

  // Pre-filter rejection reasons in plain English
  const reasonEntries = Object.entries(s.preFilter.reasons).sort((a, b) => b[1] - a[1]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
      {/* Cycle header */}
      <BentoCard>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
              {total} stocks
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 2 }}>
              being evaluated this cycle
            </div>
          </div>
          <Badge variant={s.analysis.running > 0 ? "accent" : s.gate.completed > 0 ? "success" : "neutral"} glow={s.analysis.running > 0}>
            {s.analysis.running > 0 ? "Analysing" : s.gate.pending > 0 ? "Screening" : "Complete"}
          </Badge>
        </div>
        {funnel.startedAt && (
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-sm)" }}>
            Started {new Date(funnel.startedAt).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
          </div>
        )}
      </BentoCard>

      {/* Funnel stages */}
      <BentoCard title="How stocks flow through the pipeline">
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
          <FunnelBar
            label="Data Collected"
            count={s.dataFetch.completed}
            maxCount={total}
            color="var(--color-accent-bright)"
            detail={s.dataFetch.running > 0 ? `${s.dataFetch.running} still loading...` : s.dataFetch.failed > 0 ? `${s.dataFetch.failed} couldn't be loaded` : undefined}
            tooltip="Financial data and market prices gathered for each stock"
          />

          {/* Arrow connector */}
          <div style={{ display: "flex", justifyContent: "center" }}>
            <div style={{
              width: 2,
              height: 16,
              background: "linear-gradient(to bottom, var(--color-accent-bright), var(--color-surface-3))",
              borderRadius: 1,
            }} />
          </div>

          <FunnelBar
            label="Quick Health Check"
            count={s.preFilter.passed}
            maxCount={s.preFilter.completed}
            color="var(--color-success)"
            detail={s.preFilter.rejected > 0 ? `${s.preFilter.rejected} removed — obvious red flags` : undefined}
            tooltip="Fast automated check for deal-breakers like near-bankruptcy or extreme overvaluation"
          />

          {/* Rejection reasons */}
          {reasonEntries.length > 0 && (
            <div style={{
              padding: "var(--space-sm) var(--space-md)",
              background: "rgba(248,113,113,0.04)",
              borderRadius: "var(--radius-sm)",
              borderLeft: "3px solid var(--color-error)",
            }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: "var(--color-error)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Why stocks were removed
              </div>
              {reasonEntries.map(([rule, count]) => (
                <div key={rule} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 0" }}>
                  <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
                    {PRE_FILTER_EXPLANATIONS[rule] ?? rule.replace(/_/g, " ")}
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: "var(--color-error)" }}>
                    {count}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "center" }}>
            <div style={{
              width: 2,
              height: 16,
              background: "linear-gradient(to bottom, var(--color-success), var(--color-surface-3))",
              borderRadius: 1,
            }} />
          </div>

          {/* Screener section */}
          <div>
            <FunnelBar
              label="Expert Screening"
              count={Object.values(s.screeners.stats).reduce((sum, v) => sum + (v.completed ?? 0), 0)}
              maxCount={s.screeners.totalScreenerSteps}
              color="var(--color-accent-bright)"
              tooltip="Four AI analysts each examine the stock from a different angle"
            />
            {Object.keys(s.screeners.stats).length > 0 && (
              <div style={{ display: "flex", gap: "var(--space-sm)", marginTop: "var(--space-sm)", flexWrap: "wrap" }}>
                {Object.entries(s.screeners.stats).map(([name, stats]) => {
                  const info = SCREENER_NAMES[name];
                  const done = stats.completed ?? 0;
                  const total = Object.values(stats).reduce((a, b) => a + b, 0);
                  const running = stats.running ?? 0;
                  return (
                    <Tooltip key={name} text={info?.description ?? name}>
                      <div style={{
                        padding: "4px 10px",
                        background: "var(--color-surface-1)",
                        borderRadius: "var(--radius-sm)",
                        fontSize: 10,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}>
                        <StepDot status={running > 0 ? "running" : done === total ? "completed" : "pending"} />
                        <span style={{ color: "var(--color-text-secondary)", fontWeight: 500 }}>
                          {info?.label ?? name}
                        </span>
                        <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
                          {done}/{total}
                        </span>
                      </div>
                    </Tooltip>
                  );
                })}
              </div>
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "center" }}>
            <div style={{
              width: 2,
              height: 16,
              background: "linear-gradient(to bottom, var(--color-accent-bright), var(--color-surface-3))",
              borderRadius: 1,
            }} />
          </div>

          {/* Gate decision */}
          <div style={{
            padding: "var(--space-md)",
            background: "var(--color-surface-1)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--glass-border)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-sm)" }}>
              <Tooltip text="If 3 of 4 screening experts approve, the stock advances to full analysis">
                <span style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text)" }}>
                  Screening Decision
                </span>
              </Tooltip>
              <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
                3 of 4 must approve
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-sm)" }}>
              <div style={{ textAlign: "center", padding: "var(--space-sm)", background: "rgba(52,211,153,0.06)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-success)" }}>
                  {s.gate.passed}
                </div>
                <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>Advanced</div>
              </div>
              <div style={{ textAlign: "center", padding: "var(--space-sm)", background: "rgba(248,113,113,0.06)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-error)" }}>
                  {s.gate.rejected + s.gate.preFiltered}
                </div>
                <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>Filtered Out</div>
              </div>
              <div style={{ textAlign: "center", padding: "var(--space-sm)", background: "rgba(251,191,36,0.06)", borderRadius: "var(--radius-sm)" }}>
                <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-warning)" }}>
                  {s.gate.pending}
                </div>
                <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>Waiting</div>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "center" }}>
            <div style={{
              width: 2,
              height: 16,
              background: "linear-gradient(to bottom, var(--color-success), var(--color-surface-3))",
              borderRadius: 1,
            }} />
          </div>

          {/* Deep analysis */}
          <FunnelBar
            label="Deep Analysis"
            count={s.analysis.completed}
            maxCount={s.analysis.tickers > 0 ? s.analysis.completed + s.analysis.running + s.analysis.pending + s.analysis.failed : 0}
            color="var(--gradient-active)"
            detail={
              s.analysis.tickers > 0
                ? `${s.analysis.tickers} stocks getting full team review` +
                  (s.analysis.running > 0 ? ` — ${s.analysis.running} in progress` : "") +
                  (s.analysis.failed > 0 ? ` — ${s.analysis.failed} had issues` : "")
                : "Waiting for stocks to pass screening"
            }
            tooltip="The full team of 8 investment analysts examines each stock in depth"
          />
        </div>
      </BentoCard>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ticker list (with gate outcome badges)
// ---------------------------------------------------------------------------

function GateOutcomeBadge({ outcome }: { outcome?: string | null }) {
  if (!outcome) return null;
  if (outcome === "passed") return <Badge variant="success" size="sm">Advancing</Badge>;
  if (outcome === "rejected") return <Badge variant="error" size="sm">Screened Out</Badge>;
  if (outcome === "pre_filtered") return <Badge variant="warning" size="sm">Health Check Failed</Badge>;
  return null;
}

function TickerRow({
  ticker,
  expanded,
  onToggle,
}: {
  ticker: PipelineTickerSummary;
  expanded: boolean;
  onToggle: () => void;
}) {
  const pct = ticker.total_steps > 0
    ? Math.round((ticker.completed / ticker.total_steps) * 100)
    : 0;

  return (
    <button
      onClick={onToggle}
      style={{
        width: "100%",
        padding: "var(--space-md) var(--space-lg)",
        background: expanded ? "var(--color-surface-1)" : "transparent",
        border: "none",
        borderBottom: "1px solid var(--glass-border)",
        cursor: "pointer",
        textAlign: "left",
        color: "var(--color-text)",
        fontFamily: "var(--font-sans)",
        transition: "background 0.15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
        <span style={{
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
          fontSize: "var(--text-sm)",
          minWidth: 56,
        }}>
          {ticker.ticker}
        </span>

        {/* Progress bar */}
        <div style={{
          flex: 1,
          height: 4,
          background: "var(--color-surface-2)",
          borderRadius: "var(--radius-full)",
          overflow: "hidden",
        }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            style={{
              height: "100%",
              background: ticker.failed > 0
                ? "var(--color-error)"
                : ticker.gateOutcome === "rejected" || ticker.gateOutcome === "pre_filtered"
                  ? "var(--color-warning)"
                  : "var(--gradient-active)",
              borderRadius: "var(--radius-full)",
            }}
          />
        </div>

        <GateOutcomeBadge outcome={ticker.gateOutcome} />

        <Badge
          variant={
            ticker.failed > 0 ? "error"
            : ticker.completed === ticker.total_steps && ticker.total_steps > 0 ? "success"
            : ticker.running > 0 ? "accent"
            : "neutral"
          }
          size="sm"
        >
          {ticker.completed}/{ticker.total_steps}
        </Badge>
      </div>

      {/* Pre-filter rejection inline hint */}
      {ticker.preFilter && !ticker.preFilter.passed && (
        <div style={{
          marginTop: 4,
          fontSize: 10,
          color: "var(--color-warning)",
          paddingLeft: 68,
        }}>
          {ticker.preFilter.rulesFailed.map((r) => PRE_FILTER_EXPLANATIONS[r.split(":")[0]] ?? r).join("; ")}
        </div>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Ticker detail with screener verdicts
// ---------------------------------------------------------------------------

function ScreenerVerdictCard({ screener }: { screener: PipelineScreenerVerdict }) {
  const info = SCREENER_NAMES[screener.name];
  const passed = screener.verdict === "pass";
  return (
    <div style={{
      padding: "var(--space-sm) var(--space-md)",
      background: passed ? "rgba(52,211,153,0.04)" : "rgba(248,113,113,0.04)",
      borderRadius: "var(--radius-sm)",
      borderLeft: `3px solid ${passed ? "var(--color-success)" : "var(--color-error)"}`,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
    }}>
      <div>
        <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text)" }}>
          {info?.label ?? screener.name.replace(/_/g, " ")}
        </div>
        <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 2 }}>
          {info?.description ?? ""}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
        {screener.latencyMs != null && (
          <span style={{ fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            {(screener.latencyMs / 1000).toFixed(1)}s
          </span>
        )}
        <Badge variant={passed ? "success" : "error"} size="sm">
          {passed ? "Pass" : "Fail"}
        </Badge>
      </div>
    </div>
  );
}

function TickerDetail({ ticker }: { ticker: string }) {
  const { detail, loading } = usePipelineTickerDetail(ticker);

  if (loading) {
    return (
      <div style={{ padding: "var(--space-md) var(--space-lg)" }}>
        <Skeleton height={120} />
      </div>
    );
  }

  if (!detail || detail.steps.length === 0) {
    return (
      <div style={{
        padding: "var(--space-md) var(--space-lg)",
        fontSize: "var(--text-xs)",
        color: "var(--color-text-muted)",
      }}>
        No steps found.
      </div>
    );
  }

  const screeningSteps = detail.steps.filter((s) => getStepPhase(s.step) === "screening");
  const analysisSteps = detail.steps.filter((s) => getStepPhase(s.step) === "analysis");

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      style={{ overflow: "hidden" }}
    >
      <div style={{
        padding: "var(--space-sm) var(--space-lg) var(--space-md)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-md)",
      }}>
        {/* Pre-filter result */}
        {detail.preFilter && (
          <div style={{
            padding: "var(--space-sm) var(--space-md)",
            background: detail.preFilter.passed ? "rgba(52,211,153,0.04)" : "rgba(248,113,113,0.04)",
            borderRadius: "var(--radius-sm)",
            borderLeft: `3px solid ${detail.preFilter.passed ? "var(--color-success)" : "var(--color-error)"}`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text)" }}>
                Quick Health Check
              </span>
              <Badge variant={detail.preFilter.passed ? "success" : "error"} size="sm">
                {detail.preFilter.passed ? "Passed" : "Failed"}
              </Badge>
            </div>
            {!detail.preFilter.passed && detail.preFilter.rulesFailed.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {detail.preFilter.rulesFailed.map((rule, i) => {
                  const ruleName = rule.split(":")[0].trim();
                  return (
                    <div key={i} style={{ fontSize: 11, color: "var(--color-text-secondary)", padding: "2px 0" }}>
                      {PRE_FILTER_EXPLANATIONS[ruleName] ?? rule}
                    </div>
                  );
                })}
              </div>
            )}
            <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 4 }}>
              {detail.preFilter.rulesChecked} checks run
            </div>
          </div>
        )}

        {/* Screener verdicts */}
        {detail.screeners.length > 0 && (
          <div>
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "var(--space-xs)",
            }}>
              <span style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Expert Screening
              </span>
              {detail.screenerVotes && (
                <span style={{ fontSize: 10, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                  {detail.screenerVotes.pass}/{detail.screenerVotes.total} passed (need {detail.screenerVotes.required})
                </span>
              )}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
              {detail.screeners.map((s) => (
                <ScreenerVerdictCard key={s.name} screener={s} />
              ))}
            </div>
          </div>
        )}

        {/* Gate outcome */}
        {detail.gateOutcome && (
          <div style={{
            padding: "var(--space-sm) var(--space-md)",
            background: detail.gateOutcome === "passed" ? "rgba(52,211,153,0.06)" : "rgba(248,113,113,0.06)",
            borderRadius: "var(--radius-sm)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text)" }}>
              Final Screening Result
            </span>
            <GateOutcomeBadge outcome={detail.gateOutcome} />
          </div>
        )}

        {/* Phase 1: Screening steps */}
        {screeningSteps.length > 0 && (
          <div>
            <div style={{ fontSize: 10, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
              Phase 1 — Screening
            </div>
            {screeningSteps.map((step, i) => (
              <StepRow key={i} step={step} />
            ))}
          </div>
        )}

        {/* Phase 2: Analysis steps */}
        {analysisSteps.length > 0 && (
          <div>
            <div style={{ fontSize: 10, fontWeight: 600, color: "var(--color-accent-bright)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
              Phase 2 — Deep Analysis
            </div>
            {analysisSteps.map((step, i) => (
              <StepRow key={i} step={step} />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function StepRow({ step }: { step: PipelineStepDetail }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-sm)",
        padding: "var(--space-xs) var(--space-sm)",
        borderRadius: "var(--radius-sm)",
        background: step.status === "running" ? "rgba(var(--accent-rgb, 99,102,241), 0.06)" : "transparent",
      }}
    >
      <StepDot status={step.status} />
      <span style={{
        fontSize: "var(--text-xs)",
        fontWeight: 500,
        flex: 1,
        color: step.status === "running" ? "var(--color-text)" : "var(--color-text-secondary)",
      }}>
        {formatStepName(step.step)}
      </span>
      {step.error && (
        <span style={{
          fontSize: 9,
          color: "var(--color-error)",
          maxWidth: 120,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
          title={step.error}
        >
          {step.error}
        </span>
      )}
      {step.retryCount > 0 && (
        <Badge variant="warning" size="sm">retry {step.retryCount}</Badge>
      )}
      {step.completedAt && (
        <span style={{ fontSize: 9, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
          {new Date(step.completedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Health tab
// ---------------------------------------------------------------------------

function HealthView({ health }: { health: PipelineHealth }) {
  if (!health.hasCycle) {
    return (
      <BentoCard variant="accent">
        <div style={{ textAlign: "center", padding: "var(--space-xl) 0", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
          No active cycle — health metrics will appear when the pipeline is running.
        </div>
      </BentoCard>
    );
  }

  const stepHealth = health.stepHealth ?? [];
  const stepTiming = health.stepTiming ?? [];
  const recentErrors = health.recentErrors ?? [];
  const blocks = health.reentryBlocks ?? { total: 0, active: 0 };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
      {/* Reentry blocks summary */}
      <BentoCard title="Re-entry Blocks">
        <Tooltip text="When a stock is rejected, it's blocked from re-analysis until conditions change (price drops, financials improve, or time passes)">
          <div style={{ display: "flex", gap: "var(--space-lg)" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-warning)" }}>
                {blocks.active}
              </div>
              <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>Active blocks</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-text-muted)" }}>
                {blocks.total}
              </div>
              <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>Total ever</div>
            </div>
          </div>
        </Tooltip>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: "var(--space-sm)", lineHeight: 1.4 }}>
          Stocks that were rejected get a "cooling off" period. They won't be re-evaluated until their situation genuinely changes — like a meaningful price drop or improved financials.
        </div>
      </BentoCard>

      {/* Step reliability */}
      <BentoCard title="Step Reliability">
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: "var(--space-md)", lineHeight: 1.4 }}>
          How reliably each part of the pipeline is running. Lower error rates are better.
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
          {stepHealth.map((sh) => (
            <div key={sh.step} style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              padding: "var(--space-xs) var(--space-sm)",
              background: sh.errorRate > 10 ? "rgba(248,113,113,0.04)" : "transparent",
              borderRadius: "var(--radius-sm)",
            }}>
              <span style={{ fontSize: "var(--text-xs)", flex: 1, color: "var(--color-text-secondary)", fontWeight: 500 }}>
                {formatStepName(sh.step)}
              </span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--color-text-muted)" }}>
                {sh.completed}/{sh.total}
              </span>
              <Badge variant={sh.errorRate === 0 ? "success" : sh.errorRate < 5 ? "warning" : "error"} size="sm">
                {sh.errorRate}% fail
              </Badge>
            </div>
          ))}
        </div>
      </BentoCard>

      {/* Step timing */}
      {stepTiming.length > 0 && (
        <BentoCard title="Processing Speed">
          <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: "var(--space-md)", lineHeight: 1.4 }}>
            Average time each step takes to complete. Slower steps may indicate rate limits or heavy workloads.
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
            {stepTiming.map((st) => (
              <div key={st.step} style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                padding: "var(--space-xs) var(--space-sm)",
              }}>
                <span style={{ fontSize: "var(--text-xs)", flex: 1, color: "var(--color-text-secondary)", fontWeight: 500 }}>
                  {formatStepName(st.step)}
                </span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: st.avgSeconds > 60 ? "var(--color-warning)" : "var(--color-text)" }}>
                  {st.avgSeconds < 1 ? "<1s" : st.avgSeconds < 60 ? `${st.avgSeconds.toFixed(0)}s` : `${(st.avgSeconds / 60).toFixed(1)}m`}
                </span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--color-text-muted)" }}>
                  (max {st.maxSeconds < 60 ? `${st.maxSeconds.toFixed(0)}s` : `${(st.maxSeconds / 60).toFixed(1)}m`})
                </span>
              </div>
            ))}
          </div>
        </BentoCard>
      )}

      {/* Recent errors */}
      {recentErrors.length > 0 && (
        <BentoCard title="Recent Issues" variant="error">
          <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: "var(--space-md)", lineHeight: 1.4 }}>
            The most recent problems encountered. These may resolve on their own through automatic retries.
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {recentErrors.map((err, i) => (
              <div key={i} style={{
                padding: "var(--space-sm) var(--space-md)",
                background: "rgba(248,113,113,0.04)",
                borderRadius: "var(--radius-sm)",
                borderLeft: "3px solid var(--color-error)",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--color-text)" }}>
                    {err.ticker}
                  </span>
                  <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
                    {formatStepName(err.step)}
                  </span>
                </div>
                {err.error && (
                  <div style={{ fontSize: 11, color: "var(--color-error)", marginTop: 4, lineHeight: 1.3, wordBreak: "break-word" }}>
                    {err.error}
                  </div>
                )}
                <div style={{ display: "flex", gap: "var(--space-md)", marginTop: 4, fontSize: 10, color: "var(--color-text-muted)" }}>
                  {err.at && <span>{new Date(err.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
                  {err.retries > 0 && <span>Retried {err.retries}x</span>}
                </div>
              </div>
            ))}
          </div>
        </BentoCard>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tickers tab
// ---------------------------------------------------------------------------

function TickersView({
  tickers,
  tickersLoading,
}: {
  tickers: PipelineTickerSummary[];
  tickersLoading: boolean;
}) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "passed" | "rejected" | "pending">("all");

  const filtered = tickers.filter((t) => {
    if (filter === "all") return true;
    if (filter === "passed") return t.gateOutcome === "passed";
    if (filter === "rejected") return t.gateOutcome === "rejected" || t.gateOutcome === "pre_filtered";
    if (filter === "pending") return !t.gateOutcome;
    return true;
  });

  const passedCount = tickers.filter((t) => t.gateOutcome === "passed").length;
  const rejectedCount = tickers.filter((t) => t.gateOutcome === "rejected" || t.gateOutcome === "pre_filtered").length;
  const pendingCount = tickers.filter((t) => !t.gateOutcome).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
      {/* Filter chips */}
      <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
        {([
          { key: "all", label: `All (${tickers.length})` },
          { key: "passed", label: `Advancing (${passedCount})` },
          { key: "rejected", label: `Filtered (${rejectedCount})` },
          { key: "pending", label: `In Progress (${pendingCount})` },
        ] as const).map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            style={{
              padding: "4px 12px",
              fontSize: "var(--text-xs)",
              fontWeight: filter === f.key ? 600 : 400,
              color: filter === f.key ? "var(--color-accent-bright)" : "var(--color-text-muted)",
              background: filter === f.key ? "var(--color-accent-ghost)" : "var(--color-surface-1)",
              border: filter === f.key ? "1px solid rgba(99,102,241,0.2)" : "1px solid var(--glass-border)",
              borderRadius: "var(--radius-full)",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <BentoCard>
        {tickersLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            <Skeleton height={40} />
            <Skeleton height={40} />
            <Skeleton height={40} />
          </div>
        ) : filtered.length === 0 ? (
          <div style={{
            textAlign: "center",
            padding: "var(--space-lg)",
            color: "var(--color-text-muted)",
            fontSize: "var(--text-sm)",
          }}>
            {tickers.length === 0 ? "No stocks in this cycle yet." : "No stocks match this filter."}
          </div>
        ) : (
          <div style={{ margin: "calc(-1 * var(--space-xl))", marginTop: 0 }}>
            {filtered.map((t) => (
              <div key={t.ticker}>
                <TickerRow
                  ticker={t}
                  expanded={expandedTicker === t.ticker}
                  onToggle={() =>
                    setExpandedTicker(
                      expandedTicker === t.ticker ? null : t.ticker
                    )
                  }
                />
                <AnimatePresence>
                  {expandedTicker === t.ticker && (
                    <TickerDetail ticker={t.ticker} />
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
        )}
      </BentoCard>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Pipeline view
// ---------------------------------------------------------------------------

export function Pipeline() {
  const { status, loading: statusLoading, error: statusError } = usePipelineStatus();
  const { tickers, loading: tickersLoading } = usePipelineTickers(status?.cycle?.id);
  const { funnel, loading: funnelLoading } = usePipelineFunnel();
  const { health, loading: healthLoading } = usePipelineHealth();
  const [activeTab, setActiveTab] = useState("overview");

  const cycle = status?.cycle;
  const steps = status?.steps ?? {};
  const running = steps.running ?? 0;

  const tabs = [
    { key: "overview", label: "Overview" },
    { key: "tickers", label: `Stocks (${tickers.length})` },
    { key: "health", label: "Health" },
  ];

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Pipeline"
        subtitle="How your stocks are being evaluated"
        right={
          cycle ? (
            <Badge variant={running > 0 ? "accent" : "success"} glow={running > 0}>
              {running > 0 ? "Running" : "Idle"}
            </Badge>
          ) : null
        }
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
        {statusError && (
          <BentoCard>
            <p style={{ color: "var(--color-error)", fontSize: "var(--text-sm)" }}>
              {statusError}
            </p>
          </BentoCard>
        )}

        {activeTab === "overview" && (
          funnelLoading ? (
            <>
              <Skeleton height={80} />
              <Skeleton height={300} />
            </>
          ) : funnel ? (
            <FunnelView funnel={funnel} />
          ) : null
        )}

        {activeTab === "tickers" && (
          statusLoading ? (
            <>
              <Skeleton height={40} />
              <Skeleton height={200} />
            </>
          ) : !cycle ? (
            <BentoCard variant="accent">
              <div style={{ textAlign: "center", padding: "var(--space-xl) 0", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
                No active cycle. Stocks will appear here when the pipeline starts.
              </div>
            </BentoCard>
          ) : (
            <TickersView tickers={tickers} tickersLoading={tickersLoading} />
          )
        )}

        {activeTab === "health" && (
          healthLoading ? (
            <>
              <Skeleton height={80} />
              <Skeleton height={200} />
              <Skeleton height={200} />
            </>
          ) : health ? (
            <HealthView health={health} />
          ) : null
        )}

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}
