import { useState } from "react";
import { CollapsiblePanel } from "./CollapsiblePanel";
import { Badge } from "../shared/Badge";
import { useDataReport } from "../../hooks/useDataReport";
import { useTriggerAgent, useTriggerBoard, useTriggerFull } from "../../hooks/usePipelineTrigger";
import type { DataReportAgentImpact } from "../../types/models";

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

export function DataHealthPanel({ ticker }: { ticker: string }) {
  const { report, loading } = useDataReport(ticker);
  const triggerAgent = useTriggerAgent();
  const triggerBoard = useTriggerBoard();
  const triggerFull = useTriggerFull();
  const [boardTriggering, setBoardTriggering] = useState(false);

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
                    color: "var(--color-text-muted)",
                    fontSize: 10,
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
            onClick={() => triggerFull.mutate({ tickers: [ticker], force_data_refresh: true })}
            disabled={triggerFull.isPending}
            style={{
              marginTop: "var(--space-md)",
              padding: "var(--space-xs) var(--space-md)",
              borderRadius: "var(--radius-sm)",
              background: "var(--color-surface-2)",
              border: "none",
              color: "var(--color-text-secondary)",
              cursor: triggerFull.isPending ? "wait" : "pointer",
              fontSize: "var(--text-xs)",
              fontWeight: 500,
              width: "100%",
            }}
          >
            {triggerFull.isPending ? "Refreshing..." : "Refresh All Data"}
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
              onClick={() => {
                setBoardTriggering(true);
                triggerBoard.mutate(
                  { ticker },
                  { onSettled: () => setBoardTriggering(false) },
                );
              }}
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
