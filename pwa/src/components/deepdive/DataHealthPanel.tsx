import { useState, useEffect } from "react";
import { CollapsiblePanel } from "./CollapsiblePanel";
import { Badge } from "../shared/Badge";
import { useDataReport } from "../../hooks/useDataReport";
import { useTriggerAgent, useTriggerBoard, useTriggerFull } from "../../hooks/usePipelineTrigger";
import type { DataReportAgentImpact } from "../../types/models";

interface DataHealthPanelProps {
  ticker: string;
  /** Called when pipeline activity starts/stops — drives the activity pill */
  onActivity?: (active: boolean, error?: string | null) => void;
}

const DATA_LABELS: Record<string, string> = {
  fundamentals: "Fundamentals",
  technical_indicators: "Technicals",
  macro_context: "Macro",
  news_context: "News",
  earnings_context: "Earnings",
  insider_context: "Insider Trades",
  filing_context: "SEC Filings",
  institutional_context: "Institutions",
  analyst_ratings: "Analyst Ratings",
  short_interest: "Short Interest",
  social_sentiment: "Social Sentiment",
  research_briefing: "Research Brief",
};

function timeSince(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const hrs = Math.floor((Date.now() - d.getTime()) / 3_600_000);
    if (hrs < 1) return "just now";
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return days === 1 ? "yesterday" : `${days}d ago`;
  } catch {
    return "";
  }
}

function StatusDot({ available, age }: { available: boolean; age?: string }) {
  const color = available
    ? age && new Date(age).getTime() < Date.now() - 24 * 3_600_000
      ? "var(--color-warning)"
      : "var(--color-success)"
    : "var(--color-text-muted)";

  return (
    <span
      style={{
        display: "inline-block",
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: color,
        marginRight: 6,
        flexShrink: 0,
      }}
    />
  );
}

function RefreshButton({
  onClick,
  loading,
  size = 14,
}: {
  onClick: () => void;
  loading?: boolean;
  size?: number;
}) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      disabled={loading}
      title="Re-run"
      style={{
        background: "none",
        border: "none",
        cursor: loading ? "wait" : "pointer",
        padding: 2,
        opacity: loading ? 0.4 : 0.6,
        transition: "opacity 0.15s",
        display: "inline-flex",
        alignItems: "center",
      }}
      onMouseEnter={(e) => {
        if (!loading) (e.currentTarget as HTMLElement).style.opacity = "1";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.opacity = loading ? "0.4" : "0.6";
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{
          animation: loading ? "spin 1s linear infinite" : "none",
          color: "var(--color-accent-bright)",
        }}
      >
        <path d="M21 12a9 9 0 11-6.22-8.56" />
        <polyline points="21 3 21 12 12 12" />
      </svg>
    </button>
  );
}

function AgentRow({
  agent,
  ticker,
  triggerAgent,
}: {
  agent: DataReportAgentImpact;
  ticker: string;
  triggerAgent: ReturnType<typeof useTriggerAgent>;
}) {
  const sentimentColor =
    (agent.lastConfidence ?? 0) > 0.6
      ? "var(--color-success)"
      : (agent.lastConfidence ?? 0) < 0.3
        ? "var(--color-error)"
        : "var(--color-text-secondary)";

  const isTriggering =
    triggerAgent.isPending && triggerAgent.variables?.agent === agent.agent;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-sm)",
        padding: "var(--space-xs) 0",
        borderBottom: "1px solid var(--color-surface-2)",
        fontSize: "var(--text-xs)",
      }}
    >
      <span style={{ flex: "0 0 100px", fontWeight: 500, textTransform: "capitalize" }}>
        {agent.agent}
      </span>

      {agent.lastConfidence != null ? (
        <span
          style={{
            fontFamily: "var(--font-mono)",
            color: sentimentColor,
            flex: "0 0 45px",
          }}
        >
          {agent.lastConfidence.toFixed(2)}
        </span>
      ) : (
        <span style={{ flex: "0 0 45px", color: "var(--color-text-muted)" }}>--</span>
      )}

      {agent.status === "capped" && (
        <Badge variant="warning">
          cap {agent.cap?.toFixed(2)}
        </Badge>
      )}

      <span
        style={{
          flex: 1,
          color: "var(--color-text-muted)",
          textAlign: "right",
          fontSize: "var(--text-xs)",
        }}
      >
        {agent.lastSignalAt ? timeSince(agent.lastSignalAt) : "no data"}
      </span>

      <RefreshButton
        onClick={() => triggerAgent.mutate({ ticker, agent: agent.agent })}
        loading={isTriggering}
        size={12}
      />
    </div>
  );
}

export function DataHealthPanel({ ticker, onActivity }: DataHealthPanelProps) {
  const [isActive, setIsActive] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  // Poll faster (5s) when pipeline is active, otherwise 30s
  const { report, loading } = useDataReport(ticker, isActive ? 5_000 : 30_000);

  const triggerAgent = useTriggerAgent();
  const triggerBoard = useTriggerBoard();
  const triggerFull = useTriggerFull();
  const [boardTriggering, setBoardTriggering] = useState(false);

  // Notify parent of activity changes
  useEffect(() => {
    onActivity?.(isActive, lastError);
  }, [isActive, lastError, onActivity]);

  function handleRefreshAll() {
    setLastError(null);
    setIsActive(true);
    onActivity?.(true);
    triggerFull.mutate(
      { tickers: [ticker], force_data_refresh: true },
      {
        onError: (err) => {
          const msg = err instanceof Error ? err.message : "Trigger failed";
          setLastError(msg);
          onActivity?.(true, msg);
        },
      },
    );
  }

  function handleBoardReeval() {
    setLastError(null);
    setIsActive(true);
    onActivity?.(true);
    setBoardTriggering(true);
    triggerBoard.mutate(
      { ticker },
      {
        onSuccess: () => {
          setBoardTriggering(false);
          setIsActive(false);
          onActivity?.(false);
        },
        onError: (err) => {
          setBoardTriggering(false);
          const msg = err instanceof Error ? err.message : "Board re-evaluation failed";
          setLastError(msg);
          onActivity?.(true, msg);
        },
      },
    );
  }

  if (loading || !report) {
    return (
      <CollapsiblePanel
        title="Data Health"
        preview={<span style={{ color: "var(--color-text-muted)" }}>Loading...</span>}
      >
        <div style={{ padding: "var(--space-md)", color: "var(--color-text-muted)" }}>
          Loading data report...
        </div>
      </CollapsiblePanel>
    );
  }

  const availableCount = Object.values(report.available).filter(Boolean).length;
  const totalKeys = Object.keys(report.available).length;

  return (
    <CollapsiblePanel
      title="Data Health"
      preview={
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
          {availableCount}/{totalKeys} data sources
          {report.cappedAgentCount > 0 && (
            <span style={{ color: "var(--color-warning)", marginLeft: "var(--space-sm)" }}>
              {report.cappedAgentCount} agents capped
            </span>
          )}
        </span>
      }
      variant={report.cappedAgentCount > 0 ? "warning" : "default"}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Error banner */}
        {lastError && (
          <div
            style={{
              padding: "var(--space-sm) var(--space-md)",
              borderRadius: "var(--radius-sm)",
              background: "rgba(248,113,113,0.1)",
              border: "1px solid rgba(248,113,113,0.2)",
              color: "var(--color-error)",
              fontSize: "var(--text-xs)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
            }}
          >
            <span style={{ flex: 1 }}>{lastError}</span>
            <button
              onClick={() => { setLastError(null); setIsActive(false); onActivity?.(false); }}
              style={{
                background: "none", border: "none", color: "var(--color-error)",
                cursor: "pointer", padding: 2, fontSize: "var(--text-xs)",
              }}
            >
              dismiss
            </button>
          </div>
        )}

        {/* Section 1: Data Availability */}
        <div>
          <div
            style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              marginBottom: "var(--space-sm)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Data Sources
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "var(--space-xs) var(--space-lg)",
            }}
          >
            {Object.entries(DATA_LABELS).map(([key, label]) => (
              <div
                key={key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  fontSize: "var(--text-xs)",
                }}
              >
                <StatusDot
                  available={report.available[key] ?? false}
                  age={report.dataAge[key]}
                />
                <span style={{ flex: 1 }}>{label}</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    color: report.available[key]
                      ? "var(--color-text-muted)"
                      : "var(--color-error)",
                    fontSize: 10,
                    fontWeight: report.available[key] ? 400 : 500,
                  }}
                >
                  {report.available[key]
                    ? report.dataAge[key]
                      ? timeSince(report.dataAge[key])
                      : "ok"
                    : "missing"}
                </span>
              </div>
            ))}
          </div>

          <button
            onClick={handleRefreshAll}
            disabled={triggerFull.isPending}
            style={{
              marginTop: "var(--space-md)",
              padding: "var(--space-xs) var(--space-md)",
              borderRadius: "var(--radius-sm)",
              background: triggerFull.isPending
                ? "var(--color-surface-2)"
                : isActive
                  ? "var(--color-surface-2)"
                  : "var(--color-accent-ghost)",
              border: "none",
              color: triggerFull.isPending
                ? "var(--color-text-muted)"
                : isActive
                  ? "var(--color-accent-bright)"
                  : "var(--color-accent-bright)",
              cursor: triggerFull.isPending ? "wait" : "pointer",
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              width: "100%",
            }}
          >
            {triggerFull.isPending
              ? "Queuing..."
              : isActive
                ? "Pipeline Active — Refresh All Data"
                : "Refresh All Data"}
          </button>
        </div>

        {/* Section 2: Agent Opinions */}
        <div>
          <div
            style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              marginBottom: "var(--space-sm)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Agent Opinions (latest)
          </div>
          {report.agentImpact.map((agent) => (
            <AgentRow
              key={agent.agent}
              agent={agent}
              ticker={ticker}
              triggerAgent={triggerAgent}
            />
          ))}
        </div>

        {/* Section 3: Board Actions */}
        <div>
          <div
            style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              marginBottom: "var(--space-sm)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Board
          </div>
          <div style={{ display: "flex", gap: "var(--space-sm)" }}>
            <button
              onClick={handleBoardReeval}
              disabled={boardTriggering}
              style={{
                flex: 1,
                padding: "var(--space-xs) var(--space-md)",
                borderRadius: "var(--radius-sm)",
                background: "var(--color-accent-ghost)",
                border: "none",
                color: "var(--color-accent-bright)",
                cursor: boardTriggering ? "wait" : "pointer",
                fontSize: "var(--text-xs)",
                fontWeight: 600,
              }}
            >
              {boardTriggering ? "Re-evaluating..." : "Re-evaluate Board"}
            </button>
          </div>
        </div>
      </div>
    </CollapsiblePanel>
  );
}
