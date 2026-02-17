import type { ReactNode } from "react";

type BadgeVariant = "accent" | "success" | "warning" | "error" | "neutral";

interface BadgeProps {
  variant: BadgeVariant;
  children: ReactNode;
}

const variantStyles: Record<BadgeVariant, { bg: string; color: string }> = {
  accent: { bg: "var(--color-accent-ghost)", color: "var(--color-accent-bright)" },
  success: { bg: "rgba(52, 211, 153, 0.12)", color: "var(--color-success)" },
  warning: { bg: "rgba(251, 191, 36, 0.12)", color: "var(--color-warning)" },
  error: { bg: "rgba(248, 113, 113, 0.12)", color: "var(--color-error)" },
  neutral: { bg: "var(--color-surface-2)", color: "var(--color-text-secondary)" },
};

export function Badge({ variant, children }: BadgeProps) {
  const style = variantStyles[variant];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "var(--space-xs) var(--space-md)",
        fontSize: "var(--text-xs)",
        fontWeight: 500,
        lineHeight: 1,
        borderRadius: "var(--radius-full)",
        background: style.bg,
        color: style.color,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}
