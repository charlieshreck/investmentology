import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface CollapsiblePanelProps {
  title: string;
  preview: React.ReactNode;
  badge?: React.ReactNode;
  variant?: "default" | "accent" | "warning" | "error";
  defaultOpen?: boolean;
  children: React.ReactNode;
}

const borderColors: Record<string, string> = {
  default: "var(--glass-border)",
  accent: "rgba(99,102,241,0.3)",
  warning: "rgba(251,191,36,0.3)",
  error: "rgba(248,113,113,0.3)",
};

export function CollapsiblePanel({
  title,
  preview,
  badge,
  variant = "default",
  defaultOpen = false,
  children,
}: CollapsiblePanelProps) {
  const [expanded, setExpanded] = useState(defaultOpen);

  return (
    <div style={{
      background: "var(--color-surface-1)",
      border: "1px solid var(--glass-border)",
      borderLeft: `3px solid ${borderColors[variant]}`,
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
    }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: "var(--space-md)",
          padding: "var(--space-lg)",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--color-text)",
          textAlign: "left",
          fontFamily: "var(--font-sans)",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: "var(--text-xs)",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            color: "var(--color-text-muted)",
          }}>
            {title}
          </div>
          <div style={{
            fontSize: "var(--text-sm)",
            color: "var(--color-text-secondary)",
            lineHeight: 1.4,
            marginTop: 2,
          }}>
            {preview}
          </div>
        </div>
        {badge}
        <span style={{
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
          transform: expanded ? "rotate(180deg)" : "none",
          transition: "transform 0.2s",
          flexShrink: 0,
        }}>
          ▼
        </span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div style={{
              padding: "0 var(--space-lg) var(--space-lg)",
              borderTop: "1px solid var(--glass-border)",
              paddingTop: "var(--space-md)",
            }}>
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
