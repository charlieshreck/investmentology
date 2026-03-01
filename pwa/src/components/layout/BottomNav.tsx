import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import { LayoutDashboard, Search, Star, Lightbulb, Settings } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useIsDesktop } from "../../hooks/useMediaQuery";

const navItems: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: "/", label: "Portfolio", icon: LayoutDashboard, end: true },
  { to: "/screener", label: "Screen", icon: Search },
  { to: "/watchlist", label: "Watch", icon: Star },
  { to: "/recommendations", label: "Recs", icon: Lightbulb },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function BottomNav() {
  const isDesktop = useIsDesktop();

  if (isDesktop) return <SideNav />;
  return <MobileNav />;
}

function MobileNav() {
  return (
    <nav
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: `calc(var(--nav-height) + var(--safe-bottom))`,
        paddingBottom: "var(--safe-bottom)",
        background: "rgba(8, 8, 14, 0.88)",
        backdropFilter: "blur(24px) saturate(1.6)",
        WebkitBackdropFilter: "blur(24px) saturate(1.6)",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-around",
        zIndex: 40,
      }}
    >
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          style={{ textDecoration: "none", position: "relative", flex: 1 }}
        >
          {({ isActive }) => (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 3,
                padding: "10px 0 6px",
                position: "relative",
              }}
            >
              {isActive && (
                <motion.div
                  layoutId="nav-pill"
                  style={{
                    position: "absolute",
                    inset: "4px 12px",
                    background: "var(--color-accent-ghost)",
                    borderRadius: 16,
                    border: "1px solid rgba(255,255,255,0.04)",
                  }}
                  transition={{ type: "spring", stiffness: 350, damping: 30 }}
                />
              )}
              {isActive && (
                <motion.div
                  layoutId="nav-bar"
                  style={{
                    position: "absolute",
                    top: -1,
                    width: 24,
                    height: 3,
                    borderRadius: 2,
                    background: "var(--gradient-active)",
                    boxShadow: "0 0 8px var(--color-accent-glow)",
                  }}
                  transition={{ type: "spring", stiffness: 400, damping: 35 }}
                />
              )}
              <motion.div
                animate={{ scale: isActive ? 1.15 : 1, y: isActive ? -1 : 0 }}
                transition={{ type: "spring", stiffness: 400, damping: 25 }}
                style={{ position: "relative", zIndex: 1 }}
              >
                <item.icon
                  size={22}
                  strokeWidth={isActive ? 2.2 : 1.6}
                  color={isActive ? "var(--color-accent-bright)" : "var(--color-text-muted)"}
                />
              </motion.div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? "var(--color-accent-bright)" : "var(--color-text-muted)",
                  letterSpacing: "0.02em",
                  position: "relative",
                  zIndex: 1,
                  transition: "color 0.15s ease",
                }}
              >
                {item.label}
              </span>
            </div>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function SideNav() {
  return (
    <nav
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        bottom: 0,
        width: "var(--sidebar-width)",
        background: "rgba(8, 8, 14, 0.92)",
        backdropFilter: "blur(24px) saturate(1.6)",
        WebkitBackdropFilter: "blur(24px) saturate(1.6)",
        borderRight: "1px solid rgba(255,255,255,0.06)",
        display: "flex",
        flexDirection: "column",
        padding: "var(--space-xl) 0",
        gap: 4,
        zIndex: 40,
      }}
    >
      <div
        style={{
          padding: "0 var(--space-lg) var(--space-xl)",
          fontSize: "var(--text-xs)",
          fontWeight: 700,
          color: "var(--color-accent-bright)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          fontFamily: "var(--font-mono)",
        }}
      >
        HB
      </div>

      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          style={{ textDecoration: "none" }}
        >
          {({ isActive }) => (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-md)",
                padding: "10px var(--space-lg)",
                margin: "0 var(--space-sm)",
                borderRadius: "var(--radius-sm)",
                position: "relative",
                cursor: "pointer",
                transition: "background 0.15s ease",
                background: isActive ? "var(--color-accent-ghost)" : "transparent",
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.background = "rgba(255,255,255,0.03)";
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.background = "transparent";
              }}
            >
              {isActive && (
                <motion.div
                  layoutId="side-pill"
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 6,
                    bottom: 6,
                    width: 3,
                    borderRadius: 2,
                    background: "var(--gradient-active)",
                    boxShadow: "0 0 8px var(--color-accent-glow)",
                  }}
                  transition={{ type: "spring", stiffness: 400, damping: 35 }}
                />
              )}
              <item.icon
                size={18}
                strokeWidth={isActive ? 2.2 : 1.6}
                color={isActive ? "var(--color-accent-bright)" : "var(--color-text-muted)"}
              />
              <span
                style={{
                  fontSize: "var(--text-sm)",
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? "var(--color-text)" : "var(--color-text-secondary)",
                  transition: "color 0.15s ease",
                }}
              >
                {item.label}
              </span>
            </div>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
