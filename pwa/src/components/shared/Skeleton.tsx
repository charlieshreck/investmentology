interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  className?: string;
  lines?: number;
  circle?: boolean;
}

export function Skeleton({ width, height = 16, className = "", lines, circle }: SkeletonProps) {
  if (lines) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={`skeleton ${className}`}
            style={{
              height: typeof height === "number" ? height : undefined,
              width: i === lines - 1 ? "70%" : width ?? "100%",
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`skeleton ${className}`}
      style={{
        width: width ?? "100%",
        height,
        borderRadius: circle ? "50%" : undefined,
      }}
    />
  );
}
