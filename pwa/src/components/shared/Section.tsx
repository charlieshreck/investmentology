import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, type LucideIcon } from "lucide-react";

export function Section({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  count,
}: {
  title: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  defaultOpen?: boolean;
  count?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [expanded, setExpanded] = useState(defaultOpen);
  return (
    <div>
      <button
        onClick={() => { setOpen((v) => !v); setExpanded(false); }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-sm)",
          width: "100%",
          padding: "var(--space-md) 0",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--color-text-secondary)",
          fontSize: "var(--text-sm)",
          fontWeight: 600,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        {Icon && <Icon size={14} strokeWidth={2} />}
        <span>{title}</span>
        {count != null && (
          <span style={{
            fontSize: "var(--text-2xs)",
            background: "var(--color-surface-2)",
            padding: "1px 8px",
            borderRadius: "var(--radius-full)",
            color: "var(--color-text-muted)",
            fontWeight: 500,
          }}>
            {count}
          </span>
        )}
        <span style={{ marginLeft: "auto" }}>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            onAnimationComplete={() => setExpanded(true)}
            style={{ overflow: expanded ? "visible" : "hidden" }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
