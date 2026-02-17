import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "Portfolio", icon: "P" },
  { to: "/screener", label: "Screener", icon: "S" },
  { to: "/watchlist", label: "Watch", icon: "W" },
  { to: "/recommendations", label: "Recs", icon: "R" },
  { to: "/analyze", label: "+", icon: "+" },
];

export function BottomNav() {
  return (
    <nav
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: `calc(var(--nav-height) + var(--safe-bottom))`,
        paddingBottom: "var(--safe-bottom)",
        background: "var(--glass-bg)",
        backdropFilter: `blur(var(--glass-blur))`,
        WebkitBackdropFilter: `blur(var(--glass-blur))`,
        borderTop: "1px solid var(--glass-border)",
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
          end={item.to === "/"}
          style={({ isActive }) => ({
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "var(--space-xs)",
            textDecoration: "none",
            color: isActive
              ? "var(--color-accent-bright)"
              : "var(--color-text-muted)",
            fontSize: "var(--text-xs)",
            fontWeight: isActive ? 600 : 400,
            position: "relative",
            padding: "var(--space-sm) var(--space-md)",
            transition: `color var(--duration-fast) var(--ease-out)`,
          })}
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <div
                  style={{
                    position: "absolute",
                    top: -1,
                    left: "50%",
                    transform: "translateX(-50%)",
                    width: 24,
                    height: 2,
                    background: "var(--gradient-active)",
                    borderRadius: "var(--radius-full)",
                  }}
                />
              )}
              <span
                style={{
                  fontSize: item.icon === "+" ? "var(--text-lg)" : "var(--text-base)",
                  fontWeight: item.icon === "+" ? 300 : 500,
                  fontFamily: "var(--font-mono)",
                }}
              >
                {item.icon}
              </span>
              <span>{item.label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
