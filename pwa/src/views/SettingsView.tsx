import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { useSystemHealth } from "../hooks/useSystemHealth";
import { useThemeStore, themes } from "../stores/useThemeStore";
import {
  Palette, BookOpen, Search, Plus, ScrollText,
  GraduationCap, Bot, BarChart3, Heart, LogOut,
  ChevronRight, Check,
} from "lucide-react";

export function SettingsView() {
  const { health, loading, error } = useSystemHealth();
  const navigate = useNavigate();
  const { currentTheme, setTheme } = useThemeStore();

  const dbOk = health?.database ?? false;
  const statusColor = health?.status === "healthy" ? "var(--color-success)"
    : health?.status === "degraded" ? "var(--color-warning)"
    : "var(--color-error)";

  return (
    <div style={{ height: "100%", overflowY: "auto", paddingBottom: "calc(var(--nav-height) + var(--safe-bottom) + var(--space-xl))" }}>
      <ViewHeader title="Settings" />
      <div style={{ padding: "var(--space-xl)", display: "flex", flexDirection: "column", gap: "var(--space-xl)" }}>

        {error && (
          <div style={{ padding: "var(--space-md)", background: "rgba(248,113,113,0.12)", borderRadius: "var(--radius-md)", color: "var(--color-error)", fontSize: "var(--text-sm)" }}>
            {error}
          </div>
        )}

        {/* ═══════ Theme Picker ═══════ */}
        <BentoCard variant="accent" glow>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-sm)",
            marginBottom: "var(--space-lg)",
          }}>
            <Palette size={16} color="var(--color-accent-bright)" />
            <span style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              color: "var(--color-accent-bright)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}>
              Theme
            </span>
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: "var(--space-sm)",
          }}>
            {themes.map((theme) => {
              const isActive = currentTheme.id === theme.id;
              return (
                <motion.button
                  key={theme.id}
                  onClick={() => setTheme(theme.id)}
                  whileHover={{ scale: 1.04, y: -2 }}
                  whileTap={{ scale: 0.96 }}
                  style={{
                    position: "relative",
                    padding: "var(--space-md)",
                    borderRadius: "var(--radius-lg)",
                    border: isActive
                      ? `2px solid ${theme.colors.accentBright}`
                      : "2px solid var(--glass-border)",
                    background: theme.colors.surface0,
                    cursor: "pointer",
                    textAlign: "left",
                    overflow: "hidden",
                    boxShadow: isActive
                      ? `0 0 20px ${theme.colors.accentGlow}, var(--shadow-card)`
                      : "var(--shadow-card)",
                    transition: "border-color 0.2s ease, box-shadow 0.2s ease",
                  }}
                >
                  {/* Gradient preview bar */}
                  <div style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: 3,
                    background: theme.colors.gradientActive,
                    opacity: isActive ? 1 : 0.5,
                    transition: "opacity 0.2s ease",
                  }} />

                  {/* Check mark */}
                  {isActive && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 500, damping: 25 }}
                      style={{
                        position: "absolute",
                        top: 6,
                        right: 6,
                        width: 16,
                        height: 16,
                        borderRadius: "50%",
                        background: theme.colors.gradientActive,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Check size={10} color="#fff" strokeWidth={3} />
                    </motion.div>
                  )}

                  {/* Color dots */}
                  <div style={{ display: "flex", gap: 3, marginBottom: "var(--space-sm)" }}>
                    {[theme.colors.accent, theme.colors.accentBright, theme.colors.surface2].map((c, i) => (
                      <div key={i} style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        background: c,
                        border: "1px solid rgba(255,255,255,0.08)",
                      }} />
                    ))}
                  </div>

                  <div style={{
                    fontSize: 10,
                    fontWeight: 600,
                    color: isActive ? theme.colors.accentBright : "var(--color-text-secondary)",
                    lineHeight: 1.2,
                  }}>
                    {theme.emoji} {theme.name}
                  </div>
                </motion.button>
              );
            })}
          </div>
        </BentoCard>

        {/* ═══════ System Health ═══════ */}
        <BentoCard title="System Health">
          {loading ? (
            <div className="skeleton" style={{ height: 80, borderRadius: "var(--radius-md)" }} />
          ) : health ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
                <motion.div
                  animate={{ scale: [1, 1.3, 1] }}
                  transition={{ repeat: Infinity, duration: 2 }}
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "var(--radius-full)",
                    background: statusColor,
                    boxShadow: `0 0 10px ${statusColor}`,
                  }}
                />
                <span style={{ fontSize: "var(--text-base)", fontWeight: 700, textTransform: "capitalize" }}>
                  {health.status}
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
                {[
                  { label: "Database", value: dbOk ? "Connected" : "Down", ok: dbOk },
                  { label: "Decisions", value: health.decisionsLogged.toLocaleString() },
                  { label: "Last Screen", value: health.lastQuantRun ? new Date(health.lastQuantRun).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "Never" },
                  { label: "Uptime", value: `${Math.floor(health.uptime / 3600)}h ${Math.floor((health.uptime % 3600) / 60)}m` },
                ].map((item) => (
                  <div key={item.label} style={{
                    padding: "var(--space-md)",
                    background: "var(--color-surface-1)",
                    borderRadius: "var(--radius-md)",
                  }}>
                    <div style={{ fontSize: "var(--text-2xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                      {item.label}
                    </div>
                    <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>

              {Object.keys(health.apiKeys).length > 0 && (
                <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
                  {Object.entries(health.apiKeys).map(([key, ok]) => (
                    <Badge key={key} variant={ok ? "success" : "error"} size="lg">
                      {key}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Unable to load health data.</p>
          )}
        </BentoCard>

        {/* ═══════ Navigation ═══════ */}
        <BentoCard title="Navigation">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {[
              { label: "Learning & Calibration", icon: GraduationCap, path: "/learning" },
              { label: "Run Analysis", icon: Plus, path: "/analyze" },
              { label: "Screener", icon: Search, path: "/screener" },
              { label: "Decision Log", icon: ScrollText, path: "/log" },
              { label: "Agents", icon: Bot, path: "/agents" },
              { label: "Backtest", icon: BarChart3, path: "/backtest" },
              { label: "System Health", icon: Heart, path: "/health" },
            ].map((link) => {
              const Icon = link.icon;
              return (
                <motion.button
                  key={link.path}
                  onClick={() => navigate(link.path)}
                  whileTap={{ scale: 0.98 }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-md)",
                    padding: "var(--space-md) var(--space-lg)",
                    background: "transparent",
                    border: "none",
                    borderRadius: "var(--radius-md)",
                    color: "var(--color-text)",
                    cursor: "pointer",
                    fontSize: "var(--text-sm)",
                    fontFamily: "var(--font-sans)",
                    textAlign: "left",
                    width: "100%",
                    transition: "background 0.15s ease",
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-1)"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                >
                  <Icon size={18} color="var(--color-text-muted)" />
                  <span style={{ flex: 1 }}>{link.label}</span>
                  <ChevronRight size={16} color="var(--color-text-muted)" />
                </motion.button>
              );
            })}
          </div>
        </BentoCard>

        {/* ═══════ Logout + Version ═══════ */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-lg)", padding: "var(--space-lg)" }}>
          <motion.button
            onClick={() => (window as any).__logout?.()}
            whileTap={{ scale: 0.95 }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              padding: "var(--space-md) var(--space-xl)",
              background: "rgba(248,113,113,0.1)",
              border: "1px solid rgba(248,113,113,0.2)",
              borderRadius: "var(--radius-full)",
              color: "var(--color-error)",
              cursor: "pointer",
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              fontFamily: "var(--font-sans)",
            }}
          >
            <LogOut size={16} />
            Sign Out
          </motion.button>

          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            Investmentology v0.2.0
          </span>
          <Badge variant="warning" size="lg">PAPER TRADING ONLY</Badge>
        </div>
      </div>
    </div>
  );
}
