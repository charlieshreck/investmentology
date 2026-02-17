import type { ReactNode } from "react";

interface BentoCardProps {
  title?: string;
  children: ReactNode;
  className?: string;
}

export function BentoCard({ title, children, className }: BentoCardProps) {
  return (
    <div
      className={className}
      style={{
        background: "var(--glass-bg)",
        backdropFilter: `blur(var(--glass-blur))`,
        WebkitBackdropFilter: `blur(var(--glass-blur))`,
        boxShadow: "var(--ring-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-lg)",
        border: "1px solid var(--glass-border)",
      }}
    >
      {title && (
        <h3
          style={{
            margin: `0 0 var(--space-md) 0`,
            fontSize: "var(--text-sm)",
            fontWeight: 500,
            color: "var(--color-text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}
