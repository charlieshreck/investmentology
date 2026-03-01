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

function _formatVol(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toString();
}
void _formatVol; // reserved for volume axis labels

export function PriceChart({ ticker }: { ticker: string }) {
  const [period, setPeriod] = useState<Period>("3mo");
  const [data, setData] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [scrubIdx, setScrubIdx] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Refs for direct DOM updates during scrub (no re-render per frame)
  const crosshairRef = useRef<SVGLineElement>(null);
  const dotRef = useRef<SVGCircleElement>(null);
  const priceRef = useRef<HTMLSpanElement>(null);
  const dateRef = useRef<HTMLSpanElement>(null);
  const changeRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/invest/stock/${ticker}/chart?period=${period}`)
      .then((r) => r.json())
      .then((res) => {
        if (!cancelled) {
          setData(res.data || []);
          setScrubIdx(null);
        }
      })
      .catch(() => { if (!cancelled) setData([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ticker, period]);

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

  // Convert client X to data index
  const clientXToIdx = useCallback((clientX: number): number | null => {
    if (!svgRef.current || data.length < 2) return null;
    const rect = svgRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const frac = x / rect.width;
    const idx = Math.round(frac * (data.length - 1));
    if (idx >= 0 && idx < data.length) return idx;
    return null;
  }, [data]);

  // Update crosshair + header via DOM refs (no setState during scrub)
  const updateScrub = useCallback((idx: number | null) => {
    if (idx === null || !points[idx]) {
      // Hide crosshair
      if (crosshairRef.current) crosshairRef.current.style.display = "none";
      if (dotRef.current) dotRef.current.style.display = "none";
      // Reset header to default
      if (priceRef.current) priceRef.current.textContent = "";
      if (dateRef.current) dateRef.current.textContent = "";
      if (changeRef.current) {
        changeRef.current.textContent = isPositive ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`;
        changeRef.current.style.color = isPositive ? "var(--color-success)" : "var(--color-error)";
      }
      return;
    }

    const pt = points[idx];
    const dp = data[idx];
    const scrubChange = first > 0 ? ((dp.close - first) / first) * 100 : 0;
    const scrubPositive = scrubChange >= 0;

    // Move crosshair line
    if (crosshairRef.current) {
      crosshairRef.current.setAttribute("x1", String(pt.x));
      crosshairRef.current.setAttribute("x2", String(pt.x));
      crosshairRef.current.style.display = "";
    }
    // Move dot
    if (dotRef.current) {
      dotRef.current.setAttribute("cx", String(pt.x));
      dotRef.current.setAttribute("cy", String(pt.y));
      dotRef.current.style.display = "";
    }
    // Update header: show scrubbed price + date
    if (priceRef.current) {
      priceRef.current.textContent = formatPrice(dp.close);
    }
    if (dateRef.current) {
      dateRef.current.textContent = formatDate(dp.date, period);
    }
    if (changeRef.current) {
      changeRef.current.textContent = scrubPositive ? `+${scrubChange.toFixed(2)}%` : `${scrubChange.toFixed(2)}%`;
      changeRef.current.style.color = scrubPositive ? "var(--color-success)" : "var(--color-error)";
    }
  }, [points, data, first, changePct, isPositive, period]);

  // Mouse handlers
  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const idx = clientXToIdx(e.clientX);
    setScrubIdx(idx);
    updateScrub(idx);
  }, [clientXToIdx, updateScrub]);

  const handleMouseLeave = useCallback(() => {
    setScrubIdx(null);
    updateScrub(null);
  }, [updateScrub]);

  // Touch handlers — prevent scroll while scrubbing
  const handleTouchStart = useCallback((e: React.TouchEvent<SVGSVGElement>) => {
    if (e.touches.length !== 1) return;
    const idx = clientXToIdx(e.touches[0].clientX);
    setScrubIdx(idx);
    updateScrub(idx);
  }, [clientXToIdx, updateScrub]);

  const handleTouchMove = useCallback((e: React.TouchEvent<SVGSVGElement>) => {
    if (e.touches.length !== 1) return;
    e.preventDefault(); // prevent scroll while scrubbing chart
    const idx = clientXToIdx(e.touches[0].clientX);
    setScrubIdx(idx);
    updateScrub(idx);
  }, [clientXToIdx, updateScrub]);

  const handleTouchEnd = useCallback(() => {
    setScrubIdx(null);
    updateScrub(null);
  }, [updateScrub]);

  // Scrub active state for header swap
  const isScrubbing = scrubIdx !== null;
  const scrubPoint = isScrubbing ? data[scrubIdx] : null;

  return (
    <div
      ref={containerRef}
      style={{ background: "var(--color-surface-0)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}
    >
      {/* Header — swaps between default and scrub mode */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "var(--space-md) var(--space-lg)",
          minHeight: 44,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-sm)", minWidth: 0 }}>
          {/* Scrub price — shown when scrubbing, hidden otherwise */}
          <span
            ref={priceRef}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "var(--text-lg)",
              fontWeight: 700,
              color: "var(--color-text)",
              transition: "opacity 150ms ease",
              opacity: isScrubbing ? 1 : 0,
              width: isScrubbing ? "auto" : 0,
              overflow: "hidden",
            }}
          >
            {scrubPoint ? formatPrice(scrubPoint.close) : ""}
          </span>

          {/* Label */}
          <span
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              transition: "opacity 150ms ease",
              opacity: isScrubbing ? 0 : 1,
              width: isScrubbing ? 0 : "auto",
              overflow: "hidden",
            }}
          >
            Price
          </span>

          {/* Change % — always visible, updates during scrub */}
          {!loading && prices.length > 0 && (
            <span
              ref={changeRef}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "var(--text-sm)",
                fontWeight: 700,
                color: lineColor,
              }}
            >
              {isPositive ? "+" : ""}{changePct.toFixed(2)}%
            </span>
          )}

          {/* Scrub date */}
          <span
            ref={dateRef}
            style={{
              fontSize: 10,
              color: "var(--color-text-muted)",
              fontFamily: "var(--font-mono)",
              transition: "opacity 150ms ease",
              opacity: isScrubbing ? 1 : 0,
              whiteSpace: "nowrap",
            }}
          >
            {scrubPoint ? formatDate(scrubPoint.date, period) : ""}
          </span>
        </div>

        {/* Period selector */}
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
            <div className="skeleton" style={{ width: "100%", height: H - 40, borderRadius: "var(--radius-sm)" }} />
          </div>
        ) : prices.length < 2 ? (
          <div style={{ height: H, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>No data</span>
          </div>
        ) : (
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            width="100%"
            height={H}
            style={{ display: "block", cursor: "crosshair", touchAction: "pan-y" }}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
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
                  x1={0} y1={y} x2={W} y2={y}
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

            {/* Crosshair line — positioned via ref */}
            <line
              ref={crosshairRef}
              x1={0} y1={padTop} x2={0} y2={H - padBot}
              stroke="var(--color-text-secondary)"
              strokeWidth={1}
              strokeDasharray="3 3"
              style={{ display: "none" }}
            />

            {/* Crosshair dot — positioned via ref */}
            <circle
              ref={dotRef}
              cx={0} cy={0} r={5}
              fill={lineColor}
              stroke="var(--color-surface-0)"
              strokeWidth={2.5}
              style={{ display: "none" }}
            />

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
        )}
      </div>
    </div>
  );
}
