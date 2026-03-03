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
} from "../hooks/usePipeline";
import type { PipelineTickerSummary, PipelineStepDetail } from "../types/models";

const stepStatusColors: Record<string, string> = {
  pending: "var(--color-surface-3)",
  running: "var(--color-accent)",
  completed: "var(--color-success)",
  failed: "var(--color-error)",
  expired: "var(--color-warning)",
};

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

function formatStep(step: string): string {
  if (step.startsWith("agent:")) return step.slice(6).charAt(0).toUpperCase() + step.slice(7);
  return step.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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

  const variant = ticker.failed > 0
    ? "error"
    : ticker.completed === ticker.total_steps && ticker.total_steps > 0
      ? "success"
      : ticker.running > 0
        ? "accent"
        : "neutral";

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
                : "var(--gradient-active)",
              borderRadius: "var(--radius-full)",
            }}
          />
        </div>

        <Badge variant={variant} size="sm">
          {ticker.completed}/{ticker.total_steps}
        </Badge>
      </div>
    </button>
  );
}

function TickerDetail({ ticker }: { ticker: string }) {
  const { steps, loading } = usePipelineTickerDetail(ticker);

  if (loading) {
    return (
      <div style={{ padding: "var(--space-md) var(--space-lg)" }}>
        <Skeleton height={60} />
      </div>
    );
  }

  if (steps.length === 0) {
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
        gap: "var(--space-xs)",
      }}>
        {steps.map((step: PipelineStepDetail, i: number) => (
          <div
            key={i}
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
              {formatStep(step.step)}
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
        ))}
      </div>
    </motion.div>
  );
}


export function Pipeline() {
  const { status, loading: statusLoading, error: statusError } = usePipelineStatus();
  const { tickers, loading: tickersLoading } = usePipelineTickers(
    status?.cycle?.id
  );
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  const cycle = status?.cycle;
  const steps = status?.steps ?? {};
  const totalSteps = Object.values(steps).reduce((a, b) => a + b, 0);
  const completed = steps.completed ?? 0;
  const failed = steps.failed ?? 0;
  const running = steps.running ?? 0;

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Pipeline"
        subtitle="Agent-first analysis controller"
        right={
          cycle ? (
            <Badge variant={running > 0 ? "accent" : completed > 0 ? "success" : "neutral"}>
              {running > 0 ? "Running" : "Idle"}
            </Badge>
          ) : null
        }
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
        {statusError && (
          <BentoCard>
            <p style={{ color: "var(--color-error)", fontSize: "var(--text-sm)" }}>
              {statusError}
            </p>
          </BentoCard>
        )}

        {statusLoading ? (
          <>
            <Skeleton height={100} />
            <Skeleton height={200} />
          </>
        ) : (
          <>
            {/* Cycle overview */}
            <BentoCard variant={cycle ? "default" : "accent"}>
              {!cycle ? (
                <div style={{
                  textAlign: "center",
                  padding: "var(--space-xl) 0",
                  color: "var(--color-text-muted)",
                  fontSize: "var(--text-sm)",
                }}>
                  No active pipeline cycle. The controller starts cycles automatically
                  when watchlist or quant gate candidates are ready.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
                  {/* Stats grid */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "var(--space-sm)" }}>
                    {[
                      { label: "Total", value: totalSteps, color: "var(--color-text)" },
                      { label: "Done", value: completed, color: "var(--color-success)" },
                      { label: "Running", value: running, color: "var(--color-accent-bright)" },
                      { label: "Failed", value: failed, color: "var(--color-error)" },
                    ].map((stat) => (
                      <div key={stat.label} style={{
                        padding: "var(--space-md)",
                        background: "var(--color-surface-1)",
                        borderRadius: "var(--radius-md)",
                        textAlign: "center",
                      }}>
                        <div style={{
                          fontSize: "var(--text-lg)",
                          fontWeight: 700,
                          fontFamily: "var(--font-mono)",
                          color: stat.color,
                        }}>
                          {stat.value}
                        </div>
                        <div style={{
                          fontSize: "var(--text-2xs)",
                          color: "var(--color-text-muted)",
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          marginTop: 2,
                        }}>
                          {stat.label}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Overall progress bar */}
                  {totalSteps > 0 && (
                    <div>
                      <div style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: "var(--space-xs)",
                      }}>
                        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                          Cycle progress
                        </span>
                        <span style={{
                          fontSize: "var(--text-xs)",
                          fontFamily: "var(--font-mono)",
                          fontWeight: 600,
                          color: "var(--color-text-secondary)",
                        }}>
                          {Math.round((completed / totalSteps) * 100)}%
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
                          animate={{ width: `${(completed / totalSteps) * 100}%` }}
                          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                          style={{
                            height: "100%",
                            background: "var(--gradient-active)",
                            borderRadius: "var(--radius-full)",
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Cycle meta */}
                  <div style={{
                    display: "flex",
                    gap: "var(--space-lg)",
                    fontSize: "var(--text-xs)",
                    color: "var(--color-text-muted)",
                  }}>
                    <span>Started: {new Date(cycle.startedAt).toLocaleString([], {
                      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                    })}</span>
                    <span>{cycle.tickerCount} tickers</span>
                  </div>
                </div>
              )}
            </BentoCard>

            {/* Per-ticker breakdown */}
            {cycle && (
              <BentoCard title={`Tickers (${tickers.length})`}>
                {tickersLoading ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                    <Skeleton height={40} />
                    <Skeleton height={40} />
                    <Skeleton height={40} />
                  </div>
                ) : tickers.length === 0 ? (
                  <div style={{
                    textAlign: "center",
                    padding: "var(--space-lg)",
                    color: "var(--color-text-muted)",
                    fontSize: "var(--text-sm)",
                  }}>
                    No tickers in this cycle yet.
                  </div>
                ) : (
                  <div style={{ margin: "calc(-1 * var(--space-lg))", marginTop: 0 }}>
                    {tickers.map((t: PipelineTickerSummary) => (
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
            )}
          </>
        )}

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}
