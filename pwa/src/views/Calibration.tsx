import { useEffect, useState } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { Skeleton } from "../components/shared/Skeleton";
import { apiFetch } from "../utils/apiClient";

interface VerdictAccuracy {
  total: number;
  correct: number;
  accuracy: number;
  avg_return: number;
}

interface AgentAccuracyData {
  total: number;
  correct: number;
  accuracy: number;
  avg_confidence: number;
}

interface HorizonData {
  settled: number;
  correct: number;
  accuracy: number | null;
}

interface ReliabilityPoint {
  range: string;
  predicted: number;
  actual: number;
  count: number;
}

interface CalibrationCurvePoint {
  raw: number;
  calibrated: number;
}

interface CalibrationData {
  by_verdict: Record<string, VerdictAccuracy>;
  by_agent: Record<string, AgentAccuracyData>;
  total_predictions: number;
  total_settled_90d: number;
  overall_metrics: { ece: number; brier: number; sample_count: number } | null;
  reliability_diagram: ReliabilityPoint[];
  horizon_accuracy: Record<string, HorizonData>;
  calibration_curves: Record<string, CalibrationCurvePoint[]>;
}

function AccuracyBar({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 60 ? "var(--color-success)" : pct >= 40 ? "var(--color-warning)" : "var(--color-error)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: 4 }}>
      <span style={{
        fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
        minWidth: 80, fontFamily: "var(--font-mono)", textTransform: "capitalize",
      }}>{label}</span>
      <div style={{ flex: 1, height: 10, background: "var(--color-surface-secondary)", borderRadius: 4, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`, background: color,
          borderRadius: 4, transition: "width 0.6s ease",
        }} />
      </div>
      <span style={{
        fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)",
        color: "var(--color-text-secondary)", minWidth: 44, textAlign: "right",
      }}>
        {pct}% ({total})
      </span>
    </div>
  );
}

function ReliabilityDiagram({ points }: { points: ReliabilityPoint[] }) {
  if (!points.length) return <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>No settled data yet</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", gap: 4, fontSize: 10, color: "var(--color-text-muted)", marginBottom: 4 }}>
        <span style={{ flex: 1 }}>Confidence Range</span>
        <span style={{ width: 60, textAlign: "center" }}>Predicted</span>
        <span style={{ width: 60, textAlign: "center" }}>Actual</span>
        <span style={{ width: 40, textAlign: "right" }}>N</span>
      </div>
      {points.map(p => {
        const gap = Math.abs(p.actual - p.predicted);
        const color = gap < 0.1 ? "var(--color-success)" : gap < 0.2 ? "var(--color-warning)" : "var(--color-error)";
        return (
          <div key={p.range} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ flex: 1, fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)" }}>{p.range}</span>
            <div style={{ width: 60, textAlign: "center" }}>
              <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)" }}>
                {Math.round(p.predicted * 100)}%
              </span>
            </div>
            <div style={{ width: 60, textAlign: "center" }}>
              <span style={{
                fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)",
                fontWeight: 700, color,
              }}>
                {Math.round(p.actual * 100)}%
              </span>
            </div>
            <span style={{
              width: 40, textAlign: "right", fontSize: 10,
              fontFamily: "var(--font-mono)", color: "var(--color-text-muted)",
            }}>
              {p.count}
            </span>
          </div>
        );
      })}
    </div>
  );
}

interface LeaderboardAgent {
  rank: number;
  agent: string;
  totalSettled: number;
  correct: number;
  accuracy: number;
  avgConfidence: number;
  brierScore: number;
  overconfident: boolean;
  readyForKelly: boolean;
}

interface LeaderboardData {
  agents: LeaderboardAgent[];
  totalAgents: number;
  minForKelly: number;
}

export function Calibration() {
  const [data, setData] = useState<CalibrationData | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<CalibrationData>("/api/invest/calibration"),
      apiFetch<LeaderboardData>("/api/invest/calibration/leaderboard").catch(() => null),
    ])
      .then(([cal, lb]) => { setData(cal); setLeaderboard(lb); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Skeleton lines={8} />;
  if (error) return <div style={{ color: "var(--color-error)", padding: "var(--space-lg)" }}>Error: {error}</div>;
  if (!data) return null;

  const verdictEntries = Object.entries(data.by_verdict).sort((a, b) => b[1].total - a[1].total);
  const agentEntries = Object.entries(data.by_agent).sort((a, b) => b[1].total - a[1].total);
  const horizonEntries = Object.entries(data.horizon_accuracy);

  return (
    <>
      <ViewHeader title="Calibration" subtitle="Verdict accuracy feedback loop" />

      <div style={{ display: "grid", gap: "var(--space-md)", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
        {/* Summary metrics */}
        <BentoCard title="Overview">
          <div style={{ display: "flex", gap: "var(--space-lg)", flexWrap: "wrap", marginBottom: "var(--space-md)" }}>
            <div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>Total Predictions</div>
              <div style={{ fontSize: "var(--text-xl)", fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                {data.total_predictions}
              </div>
            </div>
            <div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>Settled (90d)</div>
              <div style={{ fontSize: "var(--text-xl)", fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                {data.total_settled_90d}
              </div>
            </div>
            {data.overall_metrics && (
              <>
                <div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>ECE</div>
                  <div style={{
                    fontSize: "var(--text-xl)", fontFamily: "var(--font-mono)", fontWeight: 700,
                    color: data.overall_metrics.ece < 0.1 ? "var(--color-success)" : "var(--color-warning)",
                  }}>
                    {data.overall_metrics.ece.toFixed(3)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>Brier</div>
                  <div style={{
                    fontSize: "var(--text-xl)", fontFamily: "var(--font-mono)", fontWeight: 700,
                    color: data.overall_metrics.brier < 0.2 ? "var(--color-success)" : "var(--color-warning)",
                  }}>
                    {data.overall_metrics.brier.toFixed(3)}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Multi-horizon accuracy */}
          {horizonEntries.length > 0 && (
            <div style={{ display: "flex", gap: "var(--space-md)", flexWrap: "wrap" }}>
              {horizonEntries.map(([horizon, hd]) => (
                <Badge key={horizon} variant={hd.accuracy != null && hd.accuracy >= 0.5 ? "success" : "neutral"}>
                  {horizon}: {hd.accuracy != null ? `${Math.round(hd.accuracy * 100)}%` : "N/A"} ({hd.settled})
                </Badge>
              ))}
            </div>
          )}
        </BentoCard>

        {/* Reliability diagram */}
        <BentoCard title="Reliability Diagram">
          <ReliabilityDiagram points={data.reliability_diagram} />
        </BentoCard>

        {/* Per-verdict accuracy */}
        <BentoCard title="Verdict Accuracy (90d)">
          {verdictEntries.length === 0 ? (
            <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
              No settled verdicts yet — predictions need 90 days to settle.
            </div>
          ) : (
            verdictEntries.map(([verdict, va]) => (
              <AccuracyBar key={verdict} label={verdict} value={va.accuracy} total={va.total} />
            ))
          )}
        </BentoCard>

        {/* Per-agent accuracy */}
        <BentoCard title="Agent Accuracy (90d)">
          {agentEntries.length === 0 ? (
            <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
              No settled agent data yet.
            </div>
          ) : (
            agentEntries.map(([agent, aa]) => (
              <AccuracyBar key={agent} label={agent} value={aa.accuracy} total={aa.total} />
            ))
          )}
        </BentoCard>

        {/* Agent Leaderboard */}
        {leaderboard && leaderboard.agents.length > 0 && (
          <BentoCard title="Agent Leaderboard">
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--glass-border)" }}>
                    <th style={{ textAlign: "left", padding: "var(--space-xs) var(--space-sm)", color: "var(--color-text-muted)", fontWeight: 500 }}>#</th>
                    <th style={{ textAlign: "left", padding: "var(--space-xs) var(--space-sm)", color: "var(--color-text-muted)", fontWeight: 500 }}>Agent</th>
                    <th style={{ textAlign: "right", padding: "var(--space-xs) var(--space-sm)", color: "var(--color-text-muted)", fontWeight: 500 }}>Accuracy</th>
                    <th style={{ textAlign: "right", padding: "var(--space-xs) var(--space-sm)", color: "var(--color-text-muted)", fontWeight: 500 }}>Avg Conf</th>
                    <th style={{ textAlign: "right", padding: "var(--space-xs) var(--space-sm)", color: "var(--color-text-muted)", fontWeight: 500 }}>Brier</th>
                    <th style={{ textAlign: "right", padding: "var(--space-xs) var(--space-sm)", color: "var(--color-text-muted)", fontWeight: 500 }}>Settled</th>
                    <th style={{ textAlign: "center", padding: "var(--space-xs) var(--space-sm)", color: "var(--color-text-muted)", fontWeight: 500 }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.agents.map((a) => {
                    const accColor = a.accuracy >= 0.6 ? "var(--color-success)" : a.accuracy >= 0.45 ? "var(--color-warning)" : "var(--color-error)";
                    const brierColor = a.brierScore < 0.2 ? "var(--color-success)" : a.brierScore < 0.3 ? "var(--color-warning)" : "var(--color-error)";
                    return (
                      <tr key={a.agent} style={{ borderBottom: "1px solid var(--glass-border)" }}>
                        <td style={{ padding: "var(--space-sm)", color: "var(--color-text-muted)" }}>{a.rank}</td>
                        <td style={{ padding: "var(--space-sm)", fontWeight: 600, textTransform: "capitalize" }}>{a.agent}</td>
                        <td style={{ padding: "var(--space-sm)", textAlign: "right", color: accColor, fontWeight: 700 }}>
                          {Math.round(a.accuracy * 100)}%
                        </td>
                        <td style={{ padding: "var(--space-sm)", textAlign: "right", color: "var(--color-text-secondary)" }}>
                          {Math.round(a.avgConfidence * 100)}%
                        </td>
                        <td style={{ padding: "var(--space-sm)", textAlign: "right", color: brierColor }}>
                          {a.brierScore.toFixed(3)}
                        </td>
                        <td style={{ padding: "var(--space-sm)", textAlign: "right", color: "var(--color-text-secondary)" }}>
                          {a.totalSettled}
                        </td>
                        <td style={{ padding: "var(--space-sm)", textAlign: "center", display: "flex", gap: 4, justifyContent: "center" }}>
                          {a.overconfident && <Badge variant="warning">Overconf</Badge>}
                          {a.readyForKelly && <Badge variant="success">Kelly</Badge>}
                          {!a.readyForKelly && <Badge variant="neutral">{a.totalSettled}/{leaderboard.minForKelly}</Badge>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-sm)" }}>
              Kelly sizing activates after {leaderboard.minForKelly}+ settled predictions per agent.
              Lower Brier score = better calibrated.
            </div>
          </BentoCard>
        )}

        {/* Isotonic calibration curves */}
        {Object.keys(data.calibration_curves).length > 0 && (
          <BentoCard title="Isotonic Calibration Curves">
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-sm)" }}>
              Raw confidence vs calibrated confidence per agent
            </div>
            {Object.entries(data.calibration_curves).map(([agent, points]) => (
              <div key={agent} style={{ marginBottom: "var(--space-md)" }}>
                <div style={{
                  fontSize: "var(--text-xs)", fontWeight: 600,
                  textTransform: "capitalize", marginBottom: 4,
                }}>{agent}</div>
                <div style={{ display: "flex", gap: 2, alignItems: "end", height: 40 }}>
                  {points.map((p, i) => {
                    const diff = p.calibrated - p.raw;
                    const color = Math.abs(diff) < 0.05
                      ? "var(--color-text-muted)"
                      : diff > 0
                        ? "var(--color-success)"
                        : "var(--color-error)";
                    return (
                      <div key={i} style={{
                        flex: 1, height: `${Math.round(p.calibrated * 40)}px`,
                        background: color, borderRadius: 2, minWidth: 4,
                      }} title={`Raw: ${p.raw}, Cal: ${p.calibrated}`} />
                    );
                  })}
                </div>
              </div>
            ))}
          </BentoCard>
        )}
      </div>
    </>
  );
}
