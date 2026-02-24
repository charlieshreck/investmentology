import { useEffect, useState, useRef, useCallback } from "react";

interface ChartPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const PERIODS = ["1w", "1mo", "3mo", "6mo", "1y", "ytd"] as const;
type Period = (typeof PERIODS)[number];

const PERIOD_LABELS: Record<Period, string> = {
  "1w": "1W",
  "1mo": "1M",
  "3mo": "3M",
  "6mo": "6M",
  "1y": "1Y",
  ytd: "YTD",
};

function formatPrice(n: number): string {
  return n >= 1000 ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : `$${n.toFixed(2)}`;
}

function formatDate(dateStr: string, period: Period): string {
  const d = new Date(dateStr);
  if (period === "1w") {
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }
  if (period === "1y") {
    return d.toLocaleString(undefined, { month: "short", year: "2-digit" });
  }
  return d.toLocaleString(undefined, { month: "short", day: "numeric" });
}

function formatVol(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toString();
}

export function PriceChart({ ticker }: { ticker: string }) {
  const [period, setPeriod] = useState<Period>("3mo");
  const [data, setData] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [hover, setHover] = useState<{ idx: number; x: number; y: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/invest/stock/${ticker}/chart?period=${period}`)
      .then((r) => r.json())
      .then((res) => {
        if (!cancelled) {
          setData(res.data || []);
          setHover(null);
        }
      })
      .catch(() => { if (!cancelled) setData([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ticker, period]);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!svgRef.current || data.length < 2) return;
      const rect = svgRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const pad = 0;
      const w = rect.width - pad * 2;
      const idx = Math.round(((x - pad) / w) * (data.length - 1));
      if (idx >= 0 && idx < data.length) {
        setHover({ idx, x: e.clientX - rect.left, y: e.clientY - rect.top });
      }
    },
    [data],
  );

  const prices = data.map((d) => d.close).filter((p) => p > 0);
  const first = prices[0] ?? 0;
  const last = prices[prices.length - 1] ?? 0;
  const changePct = first > 0 ? ((last - first) / first) * 100 : 0;
  const isPositive = changePct >= 0;
  const lineColor = isPositive ? "var(--color-success)" : "var(--color-error)";

  // Chart dimensions
  const W = 600;
  const H = 200;
  const padX = 0;
  const padTop = 8;
  const padBot = 24;

  const min = prices.length > 0 ? Math.min(...prices) : 0;
  const max = prices.length > 0 ? Math.max(...prices) : 1;
  const range = max - min || 1;

  const points = prices.map((p, i) => {
    const x = padX + (i / Math.max(prices.length - 1, 1)) * (W - padX * 2);
    const y = padTop + (1 - (p - min) / range) * (H - padTop - padBot);
    return { x, y };
  });

  const polyline = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  // Gradient fill under line
  const areaPath =
    points.length > 1
      ? `M${points[0].x},${points[0].y} ` +
        points.slice(1).map((p) => `L${p.x},${p.y}`).join(" ") +
        ` L${points[points.length - 1].x},${H - padBot} L${points[0].x},${H - padBot} Z`
      : "";

  // X-axis labels
  const labelCount = 5;
  const xLabels: { x: number; label: string }[] = [];
  if (data.length >= 2) {
    for (let i = 0; i < labelCount; i++) {
      const idx = Math.round((i / (labelCount - 1)) * (data.length - 1));
      xLabels.push({
        x: points[idx]?.x ?? 0,
        label: formatDate(data[idx].date, period),
      });
    }
  }

  // Hover point data
  const hoverPoint = hover != null ? data[hover.idx] : null;

  return (
    <div style={{ background: "var(--color-surface-0)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
      {/* Period selector */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "var(--space-md) var(--space-lg)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Price
          </span>
          {!loading && prices.length > 0 && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "var(--text-sm)",
                fontWeight: 700,
                color: lineColor,
              }}
            >
              {isPositive ? "+" : ""}
              {changePct.toFixed(2)}%
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              style={{
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: period === p ? 700 : 500,
                fontFamily: "var(--font-mono)",
                background: period === p ? "var(--color-accent-ghost)" : "transparent",
                color: period === p ? "var(--color-accent-bright)" : "var(--color-text-muted)",
                border: "none",
                borderRadius: "var(--radius-full)",
                cursor: "pointer",
                transition: "all var(--duration-fast) var(--ease-out)",
              }}
            >
              {PERIOD_LABELS[p]}
            </button>
          ))}
        </div>
      </div>

      {/* Chart area */}
      <div style={{ padding: "0 var(--space-lg) var(--space-md)", position: "relative" }}>
        {loading ? (
          <div style={{ height: H, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Loading...</span>
          </div>
        ) : prices.length < 2 ? (
          <div style={{ height: H, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>No data</span>
          </div>
        ) : (
          <>
            <svg
              ref={svgRef}
              viewBox={`0 0 ${W} ${H}`}
              width="100%"
              height={H}
              style={{ display: "block", cursor: "crosshair" }}
              onMouseMove={handleMouseMove}
              onMouseLeave={() => setHover(null)}
            >
              <defs>
                <linearGradient id={`grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={lineColor} stopOpacity="0.15" />
                  <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
                </linearGradient>
              </defs>

              {/* Y gridlines */}
              {[0.25, 0.5, 0.75].map((frac) => {
                const y = padTop + frac * (H - padTop - padBot);
                return (
                  <line
                    key={frac}
                    x1={0}
                    y1={y}
                    x2={W}
                    y2={y}
                    stroke="var(--color-surface-2)"
                    strokeWidth={1}
                    strokeDasharray="4 4"
                  />
                );
              })}

              {/* Area fill */}
              {areaPath && <path d={areaPath} fill={`url(#grad-${ticker})`} />}

              {/* Price line */}
              <polyline
                points={polyline}
                fill="none"
                stroke={lineColor}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Hover crosshair */}
              {hover != null && points[hover.idx] && (
                <>
                  <line
                    x1={points[hover.idx].x}
                    y1={padTop}
                    x2={points[hover.idx].x}
                    y2={H - padBot}
                    stroke="var(--color-text-muted)"
                    strokeWidth={1}
                    strokeDasharray="3 3"
                    opacity={0.5}
                  />
                  <circle
                    cx={points[hover.idx].x}
                    cy={points[hover.idx].y}
                    r={4}
                    fill={lineColor}
                    stroke="var(--color-surface-0)"
                    strokeWidth={2}
                  />
                </>
              )}

              {/* X labels */}
              {xLabels.map((lbl, i) => (
                <text
                  key={i}
                  x={lbl.x}
                  y={H - 4}
                  textAnchor="middle"
                  fill="var(--color-text-muted)"
                  fontSize={10}
                  fontFamily="var(--font-mono)"
                >
                  {lbl.label}
                </text>
              ))}
            </svg>

            {/* Hover tooltip */}
            {hoverPoint && hover && (
              <div
                style={{
                  position: "absolute",
                  left: Math.min(hover.x + 12, W - 140),
                  top: 8,
                  background: "var(--color-surface-1)",
                  border: "1px solid var(--glass-border)",
                  borderRadius: "var(--radius-sm)",
                  padding: "var(--space-sm) var(--space-md)",
                  pointerEvents: "none",
                  zIndex: 10,
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  whiteSpace: "nowrap",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: 2 }}>{formatPrice(hoverPoint.close)}</div>
                <div style={{ color: "var(--color-text-muted)", fontSize: 10 }}>
                  O:{formatPrice(hoverPoint.open)} H:{formatPrice(hoverPoint.high)} L:{formatPrice(hoverPoint.low)}
                </div>
                <div style={{ color: "var(--color-text-muted)", fontSize: 10 }}>
                  Vol: {formatVol(hoverPoint.volume)}
                </div>
                <div style={{ color: "var(--color-text-muted)", fontSize: 9 }}>
                  {formatDate(hoverPoint.date, period)}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
