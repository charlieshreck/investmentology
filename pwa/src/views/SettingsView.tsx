import { useNavigate } from "react-router-dom";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { useSystemHealth } from "../hooks/useSystemHealth";

export function SettingsView() {
  const { health, loading, error } = useSystemHealth();
  const navigate = useNavigate();

  const dbOk = health?.database ?? false;
  const statusColor = health?.status === "healthy" ? "var(--color-success)"
    : health?.status === "degraded" ? "var(--color-warning)"
    : "var(--color-error)";

  return (
    <div style={{ height: "100%", overflowY: "auto", paddingBottom: "calc(var(--nav-height) + var(--safe-bottom) + var(--space-xl))" }}>
      <ViewHeader title="Settings" />
      <div style={{ padding: "var(--space-xl)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {error && (
          <div style={{ padding: "var(--space-md)", background: "rgba(248,113,113,0.12)", borderRadius: "var(--radius-md)", color: "var(--color-error)", fontSize: "var(--text-sm)" }}>
            {error}
          </div>
        )}

        {/* System health */}
        <BentoCard title="System Health">
          {loading ? (
            <p style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-sm)" }}>Loading health data...</p>
          ) : health ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
              {/* Overall status */}
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
                <div style={{
                  width: 10,
                  height: 10,
                  borderRadius: "var(--radius-full)",
                  background: statusColor,
                  boxShadow: `0 0 8px ${statusColor}`,
                }} />
                <span style={{ fontSize: "var(--text-base)", fontWeight: 600, textTransform: "capitalize" }}>
                  {health.status}
                </span>
              </div>

              {/* Stats */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
                <div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Database</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
                    <div style={{
                      width: 8,
                      height: 8,
                      borderRadius: "var(--radius-full)",
                      background: dbOk ? "var(--color-success)" : "var(--color-error)",
                    }} />
                    <span style={{ fontSize: "var(--text-sm)" }}>{dbOk ? "Connected" : "Disconnected"}</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Decisions Logged</div>
                  <span style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)" }}>
                    {health.decisionsLogged.toLocaleString()}
                  </span>
                </div>
                <div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Last Quant Run</div>
                  <span style={{ fontSize: "var(--text-sm)" }}>
                    {health.lastQuantRun
                      ? new Date(health.lastQuantRun).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
                      : "Never"}
                  </span>
                </div>
                <div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Uptime</div>
                  <span style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)" }}>
                    {Math.floor(health.uptime / 3600)}h {Math.floor((health.uptime % 3600) / 60)}m
                  </span>
                </div>
              </div>

              {/* API keys */}
              {Object.keys(health.apiKeys).length > 0 && (
                <div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-sm)" }}>API Keys</div>
                  <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
                    {Object.entries(health.apiKeys).map(([key, ok]) => (
                      <Badge key={key} variant={ok ? "success" : "error"}>
                        {key}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Unable to load system health.</p>
          )}
        </BentoCard>

        {/* Quick links */}
        <BentoCard title="Quick Links">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {[
              { label: "Learning & Calibration", path: "/learning" },
              { label: "Run Analysis", path: "/analyze" },
              { label: "Screener", path: "/screener" },
              { label: "Decision Log", path: "/log" },
            ].map((link) => (
              <button
                key={link.path}
                onClick={() => navigate(link.path)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "var(--space-md) var(--space-lg)",
                  background: "var(--color-surface-1)",
                  border: "1px solid var(--glass-border)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--color-text)",
                  cursor: "pointer",
                  fontSize: "var(--text-sm)",
                  fontFamily: "var(--font-sans)",
                  textAlign: "left",
                  width: "100%",
                }}
              >
                <span>{link.label}</span>
                <span style={{ color: "var(--color-text-muted)" }}>&rarr;</span>
              </button>
            ))}
          </div>
        </BentoCard>

        {/* Version info */}
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "var(--space-md)",
          padding: "var(--space-xl)",
        }}>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            Investmentology v0.1.0
          </span>
          <Badge variant="warning">PAPER TRADING ONLY</Badge>
        </div>
      </div>
    </div>
  );
}
