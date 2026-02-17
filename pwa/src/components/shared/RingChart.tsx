interface RingChartProps {
  value: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  label?: string;
}

export function RingChart({
  value,
  size = 80,
  strokeWidth = 6,
  color = "var(--color-accent)",
  label,
}: RingChartProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "var(--space-sm)",
      }}
    >
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-surface-2)"
          strokeWidth={strokeWidth}
        />
        {/* Value ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: `stroke-dashoffset var(--duration-slow) var(--ease-out)`,
          }}
        />
      </svg>
      {label && (
        <span
          style={{
            fontSize: "var(--text-xs)",
            color: "var(--color-text-secondary)",
          }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
