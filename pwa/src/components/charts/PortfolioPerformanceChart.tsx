import { useState, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../../utils/apiClient";
import { formatCurrency, formatPct, pnlColor } from "../../utils/format";

interface PerformanceData {
  dataPoints: Array<{ date: string; value: number; drawdownPct: number }>;
  cumReturn: number;
  maxDrawdown: number;
}

const PERIODS = ["1mo", "3mo", "6mo", "1y", "all"] as const;

export function PortfolioPerformanceChart() {
  const [period, setPeriod] = useState<string>("3mo");
  const [crosshair, setCrosshair] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["portfolio", "performance", period],
    queryFn: () => apiFetch<PerformanceData>(`portfolio/performance?period=${period}`),
    staleTime: 5 * 60 * 1000,
  });

  const handlePointer = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg || !data?.dataPoints.length) return;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = Math.round((x / rect.width) * (data.dataPoints.length - 1));
    setCrosshair(Math.max(0, Math.min(idx, data.dataPoints.length - 1)));
  }, [data]);

  if (isLoading) {
    return <div className="skeleton" style={{ height: 160, borderRadius: "var(--radius-md)" }} />;
  }

  if (!data?.dataPoints.length) {
    return (
      <div style={{
        padding: "var(--space-lg)",
        textAlign: "center",
        color: "var(--color-text-muted)",
        fontSize: "var(--text-xs)",
      }}>
        No performance data yet
      </div>
    );
  }

  const points = data.dataPoints;
  const W = 400, H = 140, PAD = 4;

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const toX = (i: number) => PAD + (i / (points.length - 1)) * (W - 2 * PAD);
  const toY = (v: number) => PAD + (1 - (v - min) / range) * (H - 2 * PAD);

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p.value).toFixed(1)}`)
    .join(" ");

  const areaD = `${pathD} L${toX(points.length - 1)},${H} L${toX(0)},${H} Z`;

  const isPositive = data.cumReturn >= 0;
  const lineColor = isPositive ? "var(--color-success)" : "var(--color-error)";
  const fillColor = isPositive ? "rgba(52,211,153,0.08)" : "rgba(248,113,113,0.08)";

  const hoverPoint = crosshair != null ? points[crosshair] : null;

  return (
    <div>
      {/* Period selector */}
      <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
        {PERIODS.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            style={{
              padding: "2px 8px",
              fontSize: 9,
              fontWeight: period === p ? 700 : 500,
              background: period === p ? "var(--color-surface-2)" : "transparent",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: period === p ? "var(--color-text)" : "var(--color-text-muted)",
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: "var(--space-lg)", marginBottom: 6 }}>
        <div>
          <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>
            {hoverPoint ? hoverPoint.date : "Return"}
          </div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 700, color: pnlColor(data.cumReturn) }}>
            {hoverPoint ? formatCurrency(hoverPoint.value) : formatPct(data.cumReturn)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 9, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>
            Max DD
          </div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-error)" }}>
            {formatPct(-data.maxDrawdown)}
          </div>
        </div>
      </div>

      {/* Chart */}
      <svg
        ref={svgRef}
        width="100%"
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ display: "block", cursor: "crosshair", touchAction: "none" }}
        onPointerMove={handlePointer}
        onPointerLeave={() => setCrosshair(null)}
      >
        <path d={areaD} fill={fillColor} />
        <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />

        {/* Crosshair */}
        {crosshair != null && (
          <>
            <line
              x1={toX(crosshair)} y1={0}
              x2={toX(crosshair)} y2={H}
              stroke="var(--color-text-muted)" strokeWidth={0.5} strokeDasharray="2,2" opacity={0.6}
            />
            <circle
              cx={toX(crosshair)}
              cy={toY(points[crosshair].value)}
              r={3}
              fill={lineColor}
              stroke="var(--color-surface-0)"
              strokeWidth={1.5}
            />
          </>
        )}
      </svg>
    </div>
  );
}
