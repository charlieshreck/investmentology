import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { Skeleton } from "../components/shared/Skeleton";
import { CalibrationChart } from "../components/charts/CalibrationChart";
import { useCalibration } from "../hooks/useCalibration";

interface AgentAccuracy {
  agent: string;
  accuracy: number;
  totalDecisions: number;
  avgConfidence: number;
}

interface LearningRecommendation {
  text: string;
  priority: "high" | "medium" | "low";
}

export function Learning() {
  const navigate = useNavigate();
  const { buckets, brierScore, totalPredictions, loading, error } = useCalibration();
  const [agents, setAgents] = useState<AgentAccuracy[]>([]);
  const [recommendations, setRecommendations] = useState<LearningRecommendation[]>([]);
  const [agentLoading, setAgentLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function fetchAgents() {
      try {
        const res = await fetch("/api/invest/learning/agents");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setAgents(data.agents ?? []);
          setRecommendations(data.recommendations ?? []);
        }
      } catch {
        // Agent data is supplementary, don't block on error
      } finally {
        if (!cancelled) setAgentLoading(false);
      }
    }
    fetchAgents();
    return () => { cancelled = true; };
  }, []);

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Learning"
        subtitle="Calibration & feedback"
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            <Skeleton height={200} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)" }}>
              <Skeleton height={60} />
              <Skeleton height={60} />
              <Skeleton height={60} />
            </div>
          </div>
        ) : error ? (
          <BentoCard>
            <p style={{ color: "var(--color-error)" }}>Error: {error}</p>
          </BentoCard>
        ) : (
          <>
            {/* Score Metrics */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)" }}>
              <BentoCard title="Brier Score">
                <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  {brierScore !== null ? brierScore.toFixed(3) : "N/A"}
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  Lower is better
                </div>
              </BentoCard>
              <BentoCard title="Predictions">
                <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  {totalPredictions}
                </div>
              </BentoCard>
              <BentoCard title="Buckets">
                <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  {buckets.length}
                </div>
              </BentoCard>
            </div>

            {/* Calibration Chart */}
            <BentoCard title="Calibration Plot">
              {buckets.length > 0 ? (
                <CalibrationChart buckets={buckets} />
              ) : (
                <p style={{ color: "var(--color-text-muted)", textAlign: "center", fontSize: "var(--text-sm)" }}>
                  Need more settled predictions to plot calibration.
                </p>
              )}
            </BentoCard>

            {/* Per-Bucket Accuracy */}
            {buckets.length > 0 && (
              <BentoCard title="Per-Bucket Accuracy">
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                  {buckets.map((b, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
                      <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)", minWidth: 48 }}>
                        {(b.midpoint * 100).toFixed(0)}%
                      </span>
                      <div style={{ flex: 1, height: 8, background: "var(--color-surface-2)", borderRadius: "var(--radius-full)", overflow: "hidden" }}>
                        <div
                          style={{
                            height: "100%",
                            width: `${b.accuracy * 100}%`,
                            background: Math.abs(b.accuracy - b.midpoint) < 0.1 ? "var(--color-success)" : "var(--color-warning)",
                            borderRadius: "var(--radius-full)",
                            transition: `width var(--duration-slow) var(--ease-out)`,
                          }}
                        />
                      </div>
                      <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)", minWidth: 48, textAlign: "right" }}>
                        {(b.accuracy * 100).toFixed(0)}%
                      </span>
                      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", minWidth: 24 }}>
                        n={b.count}
                      </span>
                    </div>
                  ))}
                </div>
              </BentoCard>
            )}
          </>
        )}

        {/* Agent Accuracy */}
        {!agentLoading && agents.length > 0 && (
          <BentoCard title="Agent Accuracy">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
              {agents.map((a) => (
                <div
                  key={a.agent}
                  style={{
                    padding: "var(--space-md)",
                    background: "var(--color-surface-0)",
                    borderRadius: "var(--radius-sm)",
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: "var(--text-sm)", marginBottom: "var(--space-sm)" }}>
                    {a.agent}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-xs)" }}>
                    <span style={{ color: "var(--color-text-muted)" }}>Accuracy</span>
                    <span style={{ fontFamily: "var(--font-mono)", color: a.accuracy >= 0.6 ? "var(--color-success)" : "var(--color-warning)" }}>
                      {(a.accuracy * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-xs)" }}>
                    <span style={{ color: "var(--color-text-muted)" }}>Avg Conf</span>
                    <span style={{ fontFamily: "var(--font-mono)" }}>{(a.avgConfidence * 100).toFixed(0)}%</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-xs)" }}>
                    <span style={{ color: "var(--color-text-muted)" }}>Decisions</span>
                    <span style={{ fontFamily: "var(--font-mono)" }}>{a.totalDecisions}</span>
                  </div>
                </div>
              ))}
            </div>
          </BentoCard>
        )}

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <BentoCard title="Recommendations">
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
              {recommendations.map((r, i) => (
                <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-md)" }}>
                  <Badge variant={r.priority === "high" ? "error" : r.priority === "medium" ? "warning" : "neutral"}>
                    {r.priority}
                  </Badge>
                  <span style={{ fontSize: "var(--text-sm)" }}>{r.text}</span>
                </div>
              ))}
            </div>
          </BentoCard>
        )}

        {/* Backtest link */}
        <BentoCard>
          <button
            onClick={() => navigate("/backtest")}
            style={{
              width: "100%",
              padding: "var(--space-lg)",
              background: "transparent",
              border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-accent-bright)",
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              cursor: "pointer",
              textAlign: "center",
            }}
          >
            Run Backtest — Validate Strategy Against Historical Data
          </button>
        </BentoCard>

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}
