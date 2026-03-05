import { useState, useEffect } from "react";
import { apiFetch } from "../../utils/apiClient";

export function PositionSparkline({ ticker, entryDate, avgCost }: { ticker: string; entryDate?: string; avgCost: number }) {
  const [points, setPoints] = useState<number[] | null>(null);

  useEffect(() => {
    let period = "3mo";
    if (entryDate) {
      const days = Math.floor((Date.now() - new Date(entryDate).getTime()) / 86400000);
      if (days > 365) period = "2y";
      else if (days > 180) period = "1y";
      else if (days > 90) period = "6mo";
      else period = "3mo";
    }
    apiFetch<{ data: Array<{ close: number }> }>(`stock/${ticker}/chart?period=${period}`)
      .then((data) => {
        if (data?.data?.length > 1) {
          setPoints(data.data.map((d) => d.close));
        }
      })
      .catch(() => {});
  }, [ticker, entryDate]);

  if (!points || points.length < 2) return null;

  const w = 80, h = 28;
  const min = Math.min(...points, avgCost);
  const max = Math.max(...points, avgCost);
  const range = max - min || 1;

  const toY = (v: number) => h - 2 - ((v - min) / range) * (h - 4);
  const toX = (i: number) => (i / (points.length - 1)) * w;

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p).toFixed(1)}`).join(" ");

  const trend = points[points.length - 1] >= points[0];
  const lineColor = trend ? "var(--color-success)" : "var(--color-error)";
  const fillColor = trend ? "rgba(52,211,153,0.12)" : "rgba(248,113,113,0.12)";

  const areaD = `${pathD} L${w},${h} L0,${h} Z`;
  const costY = toY(avgCost);

  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display: "block" }}>
      <path d={areaD} fill={fillColor} />
      <line x1={0} y1={costY} x2={w} y2={costY}
        stroke="var(--color-text-muted)" strokeWidth={0.5} strokeDasharray="2,2" opacity={0.4} />
      <path d={pathD} fill="none" stroke={lineColor} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={w} cy={toY(points[points.length - 1])} r={2} fill={lineColor} />
    </svg>
  );
}
