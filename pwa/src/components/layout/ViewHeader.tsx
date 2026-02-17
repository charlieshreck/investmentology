import type { ReactNode } from "react";

interface ViewHeaderProps {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}

export function ViewHeader({ title, subtitle, right }: ViewHeaderProps) {
  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 30,
        height: "var(--header-height)",
        paddingTop: "var(--safe-top)",
        paddingLeft: "var(--space-xl)",
        paddingRight: "var(--space-xl)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "var(--glass-bg)",
        backdropFilter: `blur(var(--glass-blur))`,
        WebkitBackdropFilter: `blur(var(--glass-blur))`,
        borderBottom: "1px solid var(--glass-border)",
      }}
    >
      <div>
        <h1
          style={{
            margin: 0,
            fontSize: "var(--text-lg)",
            fontWeight: 600,
            lineHeight: 1.2,
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-xs)",
              color: "var(--color-text-secondary)",
              lineHeight: 1.2,
            }}
          >
            {subtitle}
          </p>
        )}
      </div>
      {right && <div>{right}</div>}
    </header>
  );
}
