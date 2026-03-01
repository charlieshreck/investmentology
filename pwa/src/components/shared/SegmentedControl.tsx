import { motion } from "framer-motion";

interface Segment {
  id: string;
  label: string;
  count?: number;
}

interface SegmentedControlProps {
  segments: Segment[];
  activeId: string;
  onChange: (id: string) => void;
}

export function SegmentedControl({ segments, activeId, onChange }: SegmentedControlProps) {
  return (
    <div style={{
      display: "flex",
      gap: 2,
      padding: 3,
      background: "var(--color-surface-0)",
      borderRadius: "var(--radius-full)",
      border: "1px solid var(--glass-border)",
      position: "relative",
      overflow: "hidden",
    }}>
      {segments.map((seg) => {
        const isActive = seg.id === activeId;
        return (
          <button
            key={seg.id}
            onClick={() => onChange(seg.id)}
            style={{
              position: "relative",
              flex: 1,
              padding: "8px 12px",
              fontSize: "var(--text-xs)",
              fontWeight: isActive ? 700 : 500,
              fontFamily: "var(--font-sans)",
              color: isActive ? "var(--color-text-primary)" : "var(--color-text-muted)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              borderRadius: "var(--radius-full)",
              zIndex: 1,
              transition: "color 0.2s ease",
              whiteSpace: "nowrap",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 4,
            }}
          >
            {isActive && (
              <motion.div
                layoutId="segment-pill"
                style={{
                  position: "absolute",
                  inset: 0,
                  background: "var(--color-surface-2)",
                  borderRadius: "var(--radius-full)",
                  border: "1px solid var(--glass-border-light)",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.3), 0 0 12px var(--color-accent-glow)",
                }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
            <span style={{ position: "relative", zIndex: 1 }}>{seg.label}</span>
            {seg.count != null && (
              <span style={{
                position: "relative",
                zIndex: 1,
                fontSize: 9,
                fontWeight: 600,
                padding: "1px 5px",
                borderRadius: "var(--radius-full)",
                background: isActive ? "var(--color-accent-ghost)" : "transparent",
                color: isActive ? "var(--color-accent-bright)" : "var(--color-text-muted)",
                transition: "all 0.2s ease",
              }}>
                {seg.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
