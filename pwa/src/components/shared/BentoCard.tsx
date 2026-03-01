import { motion } from "framer-motion";
import type { ReactNode } from "react";

type CardVariant = "default" | "hero" | "accent" | "success" | "error";

interface BentoCardProps {
  title?: string;
  children: ReactNode;
  className?: string;
  delay?: number;
  interactive?: boolean;
  variant?: CardVariant;
  compact?: boolean;
  glow?: boolean;
}

const variantStyles: Record<CardVariant, {
  bg: string;
  border: string;
  shadow: string;
  titleColor: string;
  innerGlow: string;
  hoverBorder?: string;
}> = {
  default: {
    bg: "var(--color-surface-0)",
    border: "1px solid var(--glass-border)",
    shadow: "var(--shadow-card), inset 0 1px 0 rgba(255,255,255,0.03)",
    titleColor: "var(--color-text-muted)",
    innerGlow: "none",
  },
  hero: {
    bg: "linear-gradient(135deg, var(--color-surface-0) 0%, rgba(99,102,241,0.06) 100%)",
    border: "1px solid rgba(99,102,241,0.15)",
    shadow: "var(--shadow-card), var(--shadow-glow-accent), inset 0 1px 0 rgba(255,255,255,0.05)",
    titleColor: "var(--color-accent-bright)",
    innerGlow: "inset 0 0 60px rgba(99,102,241,0.04)",
    hoverBorder: "rgba(99,102,241,0.3)",
  },
  accent: {
    bg: "var(--color-surface-0)",
    border: "1px solid rgba(99,102,241,0.2)",
    shadow: "var(--shadow-card), inset 0 1px 0 rgba(99,102,241,0.06)",
    titleColor: "var(--color-accent-bright)",
    innerGlow: "inset 0 0 40px rgba(99,102,241,0.03)",
    hoverBorder: "rgba(99,102,241,0.35)",
  },
  success: {
    bg: "var(--color-surface-0)",
    border: "1px solid rgba(52,211,153,0.15)",
    shadow: "var(--shadow-card), var(--shadow-glow-success), inset 0 1px 0 rgba(52,211,153,0.06)",
    titleColor: "var(--color-success)",
    innerGlow: "inset 0 0 40px rgba(52,211,153,0.03)",
    hoverBorder: "rgba(52,211,153,0.3)",
  },
  error: {
    bg: "var(--color-surface-0)",
    border: "1px solid rgba(248,113,113,0.15)",
    shadow: "var(--shadow-card), var(--shadow-glow-error), inset 0 1px 0 rgba(248,113,113,0.06)",
    titleColor: "var(--color-error)",
    innerGlow: "inset 0 0 40px rgba(248,113,113,0.03)",
    hoverBorder: "rgba(248,113,113,0.3)",
  },
};

export function BentoCard({
  title,
  children,
  className,
  delay = 0,
  interactive,
  variant = "default",
  compact,
  glow,
}: BentoCardProps) {
  const v = variantStyles[variant];
  const isGradientBg = v.bg.startsWith("linear-gradient");

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-30px" }}
      transition={{
        duration: 0.45,
        delay,
        ease: [0.16, 1, 0.3, 1],
      }}
      whileHover={interactive ? {
        y: -4,
        scale: 1.01,
        transition: { type: "spring", stiffness: 300, damping: 20 },
      } : undefined}
      whileTap={interactive ? { scale: 0.98 } : undefined}
      style={{
        background: isGradientBg ? undefined : v.bg,
        backgroundImage: isGradientBg ? v.bg : undefined,
        boxShadow: glow
          ? `${v.shadow}, var(--shadow-glow-accent), ${v.innerGlow}`
          : `${v.shadow}, ${v.innerGlow}`,
        borderRadius: "var(--radius-lg)",
        padding: compact ? "var(--space-md) var(--space-lg)" : "var(--space-xl)",
        border: v.border,
        cursor: interactive ? "pointer" : undefined,
        overflow: "hidden",
        position: "relative",
        transition: "border-color 0.3s ease, box-shadow 0.3s ease",
      }}
    >
      {/* Top highlight line for hero/accent variants */}
      {(variant === "hero" || variant === "accent") && (
        <div style={{
          position: "absolute",
          top: 0,
          left: "10%",
          right: "10%",
          height: 1,
          background: "linear-gradient(90deg, transparent, var(--color-accent-bright), transparent)",
          opacity: 0.2,
        }} />
      )}

      {title && (
        <div
          style={{
            margin: `0 0 ${compact ? "var(--space-sm)" : "var(--space-md)"} 0`,
            fontSize: "var(--text-xs)",
            fontWeight: 600,
            color: v.titleColor,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          {title}
        </div>
      )}
      {children}
    </motion.div>
  );
}
