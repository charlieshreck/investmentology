import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

type BadgeVariant = "accent" | "success" | "warning" | "error" | "neutral";
type BadgeSize = "sm" | "md" | "lg";

interface BadgeProps {
  variant: BadgeVariant;
  children: ReactNode;
  icon?: LucideIcon;
  size?: BadgeSize;
  glow?: boolean;
}

const variantStyles: Record<BadgeVariant, { bg: string; color: string; border: string; glowShadow: string }> = {
  accent: {
    bg: "var(--color-accent-ghost)",
    color: "var(--color-accent-bright)",
    border: "1px solid rgba(99,102,241,0.15)",
    glowShadow: "0 0 12px var(--color-accent-glow)",
  },
  success: {
    bg: "rgba(52, 211, 153, 0.10)",
    color: "var(--color-success)",
    border: "1px solid rgba(52,211,153,0.15)",
    glowShadow: "0 0 12px rgba(52,211,153,0.15)",
  },
  warning: {
    bg: "rgba(251, 191, 36, 0.10)",
    color: "var(--color-warning)",
    border: "1px solid rgba(251,191,36,0.15)",
    glowShadow: "0 0 12px rgba(251,191,36,0.15)",
  },
  error: {
    bg: "rgba(248, 113, 113, 0.10)",
    color: "var(--color-error)",
    border: "1px solid rgba(248,113,113,0.15)",
    glowShadow: "0 0 12px rgba(248,113,113,0.15)",
  },
  neutral: {
    bg: "var(--color-surface-2)",
    color: "var(--color-text-secondary)",
    border: "1px solid var(--glass-border)",
    glowShadow: "none",
  },
};

const sizeStyles: Record<BadgeSize, { padding: string; fontSize: string; iconSize: number; fontWeight: number; letterSpacing: string }> = {
  sm: { padding: "2px 8px", fontSize: "10px", iconSize: 10, fontWeight: 500, letterSpacing: "0" },
  md: { padding: "4px 12px", fontSize: "var(--text-xs)", iconSize: 12, fontWeight: 600, letterSpacing: "0.02em" },
  lg: { padding: "8px 18px", fontSize: "var(--text-sm)", iconSize: 14, fontWeight: 700, letterSpacing: "0.03em" },
};

export function Badge({ variant, children, icon: Icon, size = "md", glow }: BadgeProps) {
  const vStyle = variantStyles[variant];
  const sStyle = sizeStyles[size];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: sStyle.padding,
        fontSize: sStyle.fontSize,
        fontWeight: sStyle.fontWeight,
        letterSpacing: sStyle.letterSpacing,
        lineHeight: 1,
        borderRadius: "var(--radius-full)",
        background: vStyle.bg,
        color: vStyle.color,
        border: vStyle.border,
        whiteSpace: "nowrap",
        boxShadow: glow ? vStyle.glowShadow : "none",
        backdropFilter: "blur(8px)",
      }}
    >
      {Icon && <Icon size={sStyle.iconSize} />}
      {children}
    </span>
  );
}
