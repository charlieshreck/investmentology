import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { useSystemHealth } from "../hooks/useSystemHealth";

function statusVariant(ok: boolean): "success" | "error" {
  return ok ? "success" : "error";
}

export function SystemHealth() {
  const { health, loading, error } = useSystemHealth();

  if (loading) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="System Health" />
        <div style={{ padding: "var(--space-xl)" }}>
          <p style={{ color: "var(--color-text-muted)" }}>Checking system health...</p>
        </div>
      </div>
    );
  }

  if (error || !health) {
    return (
      <div style={{ height: "100%", overflowY: "auto" }}>
        <ViewHeader title="System Health" />
        <div style={{ padding: "var(--space-xl)" }}>
          <BentoCard>
            <p style={{ color: "var(--color-error)" }}>
              {error ?? "Unable to reach health endpoint"}
            </p>
          </BentoCard>
        </div>
      </div>
    );
  }

  const overallVariant = health.status === "healthy" ? "success" : health.status === "degraded" ? "warning" : "error";

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="System Health"
        right={<Badge variant={overallVariant}>{health.status}</Badge>}
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Core Services */}
        <BentoCard title="Core Services">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "var(--text-sm)" }}>Database</span>
              <Badge variant={statusVariant(health.database)}>
                {health.database ? "Connected" : "Down"}
              </Badge>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "var(--text-sm)" }}>Decisions Logged</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>
                {health.decisionsLogged.toLocaleString()}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "var(--text-sm)" }}>Uptime</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>
                {formatUptime(health.uptime)}
              </span>
            </div>
            {health.lastQuantRun && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "var(--text-sm)" }}>Last Quant Run</span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
                  {new Date(health.lastQuantRun).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </BentoCard>

        {/* API Keys */}
        <BentoCard title="API Keys">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            {Object.entries(health.apiKeys).map(([key, valid]) => (
              <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "var(--text-sm)" }}>{key}</span>
                <Badge variant={statusVariant(valid)}>
                  {valid ? "Valid" : "Invalid"}
                </Badge>
              </div>
            ))}
            {Object.keys(health.apiKeys).length === 0 && (
              <p style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>No API keys configured</p>
            )}
          </div>
        </BentoCard>

        {/* Session */}
        <BentoCard title="Session">
          <button
            onClick={() => {
              if ((window as any).__logout) (window as any).__logout();
            }}
            style={{
              padding: "var(--space-sm) var(--space-lg)",
              background: "var(--color-surface-2)",
              border: "1px solid var(--color-error)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-error)",
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Sign Out
          </button>
        </BentoCard>

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
