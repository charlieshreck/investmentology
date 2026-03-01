import { type ReactNode } from "react";
import { motion } from "framer-motion";

interface Tab {
  key: string;
  label: string;
}

interface ViewHeaderProps {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  tabs?: Tab[];
  activeTab?: string;
  onTabChange?: (key: string) => void;
}

/**
 * Slim contextual header. Title is optional — bottom nav already shows
 * which page we're on, so most views just use subtitle + right slot.
 */
export function ViewHeader({ title, subtitle, right, tabs, activeTab, onTabChange }: ViewHeaderProps) {
  const hasContent = title || subtitle || right || (tabs && tabs.length > 0);
  if (!hasContent) return null;

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 30,
        paddingTop: "var(--safe-top)",
        background: "rgba(10, 10, 18, 0.8)",
        backdropFilter: "blur(20px) saturate(1.5)",
        WebkitBackdropFilter: "blur(20px) saturate(1.5)",
        borderBottom: "1px solid var(--glass-border)",
      }}
    >
      <div
        style={{
          minHeight: title ? "var(--header-height)" : 36,
          paddingLeft: "var(--space-xl)",
          paddingRight: "var(--space-xl)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          {title && (
            <h1
              style={{
                margin: 0,
                fontSize: "var(--text-xl)",
                fontWeight: 700,
                lineHeight: 1.2,
                letterSpacing: "-0.01em",
              }}
            >
              {title}
            </h1>
          )}
          {subtitle && (
            <p
              style={{
                margin: 0,
                fontSize: "var(--text-xs)",
                color: "var(--color-text-muted)",
                lineHeight: 1.2,
                marginTop: title ? 2 : 0,
              }}
            >
              {subtitle}
            </p>
          )}
        </div>
        {right && <div style={{ flexShrink: 0 }}>{right}</div>}
      </div>

      {tabs && tabs.length > 0 && (
        <div
          style={{
            display: "flex",
            gap: 2,
            padding: "0 var(--space-xl) var(--space-sm)",
            overflowX: "auto",
          }}
        >
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => onTabChange?.(tab.key)}
              style={{
                position: "relative",
                padding: "var(--space-sm) var(--space-lg)",
                fontSize: "var(--text-sm)",
                fontWeight: activeTab === tab.key ? 600 : 400,
                color: activeTab === tab.key ? "var(--color-text)" : "var(--color-text-muted)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "color 0.15s ease",
              }}
            >
              {tab.label}
              {activeTab === tab.key && (
                <motion.div
                  layoutId="tab-indicator"
                  style={{
                    position: "absolute",
                    bottom: 0,
                    left: "var(--space-lg)",
                    right: "var(--space-lg)",
                    height: 2,
                    background: "var(--gradient-active)",
                    borderRadius: "var(--radius-full)",
                  }}
                  transition={{ type: "spring", stiffness: 400, damping: 35 }}
                />
              )}
            </button>
          ))}
        </div>
      )}
    </header>
  );
}
