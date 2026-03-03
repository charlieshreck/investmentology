import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { Skeleton } from "../components/shared/Skeleton";
import { CalibrationChart } from "../components/charts/CalibrationChart";
import { useCalibration } from "../hooks/useCalibration";
import { useAttribution } from "../hooks/useToday";
import type { AgentAttribution, SignalPerf } from "../hooks/useToday";

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

function AccuracyBar({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 60 ? "var(--color-success)" : pct >= 40 ? "var(--color-warning)" : "var(--color-error)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
      <span style={{ fontSize: 10, color: "var(--color-text-muted)", minWidth: 32 }}>{label}</span>
      <div style={{ flex: 1, height: 8, background: "var(--color-surface-2)", borderRadius: 4, overflow: "hidden" }}>
        <div style={{
          height: "100%",
          width: `${pct}%`,
          background: color,
          borderRadius: 4,
          transition: "width 0.6s ease",
        }} />
      </div>
      <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)", minWidth: 36, textAlign: "right" }}>
        {pct}%
      </span>
      <span style={{ fontSize: 9, color: "var(--color-text-muted)", minWidth: 20, textAlign: "right" }}>
        n={total}
      </span>
    </div>
  );
}

function AgentAttributionCard({ name, attr }: { name: string; attr: AgentAttribution }) {
  const pct = Math.round(attr.accuracy * 100);
  const color = pct >= 60 ? "var(--color-success)" : pct >= 40 ? "var(--color-warning)" : "var(--color-error)";

  return (
    <div style={{
      padding: "var(--space-md)",
      background: "var(--color-surface-0)",
      borderRadius: "var(--radius-sm)",
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: "var(--space-sm)",
      }}>
        <span style={{ fontWeight: 600, fontSize: "var(--text-sm)", textTransform: "capitalize" }}>
          {name.replace(/_/g, " ")}
        </span>
        <span style={{
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
          fontSize: "var(--text-base)",
          color,
        }}>
          {pct}%
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <AccuracyBar label="Bull" value={attr.bullish_accuracy} total={attr.bullish_total} />
        <AccuracyBar label="Bear" value={attr.bearish_accuracy} total={attr.bearish_total} />
      </div>
      <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: "var(--space-xs)" }}>
        {attr.total_calls} total calls
      </div>
    </div>
  );
}

function SignalTagRow({ sig, variant }: { sig: SignalPerf; variant: "top" | "worst" }) {
  const pct = Math.round(sig.accuracy * 100);
  const color = variant === "top" ? "var(--color-success)" : "var(--color-error)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", padding: "var(--space-xs) 0" }}>
      <span style={{
        padding: "1px var(--space-sm)",
        fontSize: 10,
        fontFamily: "var(--font-mono)",
        background: "var(--color-surface-0)",
        border: `1px solid ${color}`,
        borderRadius: "var(--radius-sm)",
        color,
      }}>
        {sig.signal.replace(/_/g, " ")}
      </span>
      <span style={{ fontSize: 10, color: "var(--color-text-muted)", textTransform: "capitalize" }}>
        {sig.agent.replace(/_/g, " ")}
      </span>
      <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 10, fontWeight: 600, color }}>
        {pct}%
      </span>
    </div>
  );
}

export function Learning() {
  const navigate = useNavigate();
  const { buckets, brierScore, totalPredictions, loading, error } = useCalibration();
  const [agents, setAgents] = useState<AgentAccuracy[]>([]);
  const [recommendations, setRecommendations] = useState<LearningRecommendation[]>([]);
  const [agentLoading, setAgentLoading] = useState(true);
  const { data: attribution, loading: attrLoading } = useAttribution();

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

        {/* Agent Attribution — from /learning/attribution */}
        {!attrLoading && attribution && attribution.status === "ok" && Object.keys(attribution.agents).length > 0 && (
          <>
            <BentoCard title="Agent Attribution — Bullish vs Bearish">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
                {Object.entries(attribution.agents)
                  .sort(([, a], [, b]) => b.accuracy - a.accuracy)
                  .map(([name, attr]) => (
                    <AgentAttributionCard key={name} name={name} attr={attr} />
                  ))}
              </div>
            </BentoCard>

            {/* Top / Worst signal tags */}
            {(attribution.top_signals.length > 0 || attribution.worst_signals.length > 0) && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
                {attribution.top_signals.length > 0 && (
                  <BentoCard title="Best Signals">
                    {attribution.top_signals.slice(0, 5).map((sig, i) => (
                      <SignalTagRow key={i} sig={sig} variant="top" />
                    ))}
                  </BentoCard>
                )}
                {attribution.worst_signals.length > 0 && (
                  <BentoCard title="Worst Signals">
                    {attribution.worst_signals.slice(0, 5).map((sig, i) => (
                      <SignalTagRow key={i} sig={sig} variant="worst" />
                    ))}
                  </BentoCard>
                )}
              </div>
            )}

            {/* Attribution recommendations */}
            {attribution.recommendations.length > 0 && (
              <BentoCard title="Attribution Insights">
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                  {attribution.recommendations.map((r, i) => (
                    <div key={i} style={{
                      fontSize: "var(--text-sm)",
                      color: "var(--color-text-secondary)",
                      lineHeight: 1.5,
                      paddingLeft: "var(--space-md)",
                      borderLeft: "2px solid var(--color-accent-bright)",
                    }}>
                      {r}
                    </div>
                  ))}
                </div>
              </BentoCard>
            )}
          </>
        )}

        {!attrLoading && attribution && attribution.status === "insufficient_data" && (
          <BentoCard title="Agent Attribution">
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)", textAlign: "center" }}>
              {attribution.message ?? "Need more settled decisions for attribution analysis."}
            </p>
          </BentoCard>
        )}

        {/* Legacy Agent Accuracy (from /learning/agents) */}
        {!agentLoading && agents.length > 0 && (
          <BentoCard title="Agent Accuracy (Legacy)">
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
