import type { CalibrationBucket } from "../../types/models";

interface CalibrationChartProps {
  buckets: CalibrationBucket[];
}

const CHART_SIZE = 240;
const PADDING = 32;
const PLOT = CHART_SIZE - PADDING * 2;

export function CalibrationChart({ buckets }: CalibrationChartProps) {
  return (
    <svg
      width={CHART_SIZE}
      height={CHART_SIZE}
      viewBox={`0 0 ${CHART_SIZE} ${CHART_SIZE}`}
      style={{ display: "block", margin: "0 auto" }}
    >
      {/* Grid lines */}
      {[0, 25, 50, 75, 100].map((v) => {
        const y = PADDING + PLOT - (v / 100) * PLOT;
        const x = PADDING + (v / 100) * PLOT;
        return (
          <g key={v}>
            <line
              x1={PADDING}
              y1={y}
              x2={PADDING + PLOT}
              y2={y}
              stroke="var(--color-surface-2)"
              strokeWidth={0.5}
            />
            <line
              x1={x}
              y1={PADDING}
              x2={x}
              y2={PADDING + PLOT}
              stroke="var(--color-surface-2)"
              strokeWidth={0.5}
            />
            {/* Y-axis labels */}
            <text
              x={PADDING - 4}
              y={y + 3}
              textAnchor="end"
              fontSize={9}
              fill="var(--color-text-muted)"
            >
              {v}%
            </text>
            {/* X-axis labels */}
            <text
              x={x}
              y={PADDING + PLOT + 14}
              textAnchor="middle"
              fontSize={9}
              fill="var(--color-text-muted)"
            >
              {v}%
            </text>
          </g>
        );
      })}

      {/* Perfect calibration diagonal */}
      <line
        x1={PADDING}
        y1={PADDING + PLOT}
        x2={PADDING + PLOT}
        y2={PADDING}
        stroke="var(--color-text-muted)"
        strokeWidth={1}
        strokeDasharray="4 4"
      />

      {/* Actual calibration dots */}
      {buckets.map((b, i) => {
        const cx = PADDING + (b.midpoint / 100) * PLOT;
        const cy = PADDING + PLOT - (b.accuracy / 100) * PLOT;
        const r = Math.max(4, Math.min(10, Math.sqrt(b.count) * 2));
        return (
          <g key={i}>
            <circle
              cx={cx}
              cy={cy}
              r={r}
              fill="var(--color-accent)"
              opacity={0.8}
            />
            <circle
              cx={cx}
              cy={cy}
              r={r + 2}
              fill="none"
              stroke="var(--color-accent-glow)"
              strokeWidth={1}
            />
          </g>
        );
      })}

      {/* Axis labels */}
      <text
        x={CHART_SIZE / 2}
        y={CHART_SIZE - 2}
        textAnchor="middle"
        fontSize={10}
        fill="var(--color-text-secondary)"
      >
        Predicted
      </text>
      <text
        x={10}
        y={CHART_SIZE / 2}
        textAnchor="middle"
        fontSize={10}
        fill="var(--color-text-secondary)"
        transform={`rotate(-90, 10, ${CHART_SIZE / 2})`}
      >
        Actual
      </text>
    </svg>
  );
}
