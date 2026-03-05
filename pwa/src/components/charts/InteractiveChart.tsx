import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";
import type { IChartApi, ISeriesApi, CandlestickData, HistogramData, Time } from "lightweight-charts";

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

type ChartMode = "candle" | "line";

interface ChartPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export function InteractiveChart({ ticker }: { ticker: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const [period, setPeriod] = useState<Period>("3mo");
  const [mode, setMode] = useState<ChartMode>("candle");
  const [data, setData] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState(true);

  // Header stats
  const prices = data.map((d) => d.close).filter((p) => p > 0);
  const first = prices[0] ?? 0;
  const last = prices[prices.length - 1] ?? 0;
  const changePct = first > 0 ? ((last - first) / first) * 100 : 0;
  const isPositive = changePct >= 0;

  // Fetch data
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/invest/stock/${ticker}/chart?period=${period}`)
      .then((r) => r.json())
      .then((res) => {
        if (!cancelled) setData(res.data || []);
      })
      .catch(() => {
        if (!cancelled) setData([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticker, period]);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(240, 240, 248, 0.50)",
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(240, 240, 248, 0.04)" },
        horzLines: { color: "rgba(240, 240, 248, 0.04)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(99, 102, 241, 0.3)", width: 1, style: 2 },
        horzLine: { color: "rgba(99, 102, 241, 0.3)", width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: "rgba(240, 240, 248, 0.06)",
      },
      timeScale: {
        borderColor: "rgba(240, 240, 248, 0.06)",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: false },
    });

    chartRef.current = chart;

    // Resize observer
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (width > 0) chart.applyOptions({ width });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      lineSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, []);

  // Update series when data or mode changes
  const updateSeries = useCallback(() => {
    const chart = chartRef.current;
    if (!chart || data.length < 2) return;

    // Remove old series
    if (candleSeriesRef.current) {
      chart.removeSeries(candleSeriesRef.current);
      candleSeriesRef.current = null;
    }
    if (lineSeriesRef.current) {
      chart.removeSeries(lineSeriesRef.current);
      lineSeriesRef.current = null;
    }
    if (volumeSeriesRef.current) {
      chart.removeSeries(volumeSeriesRef.current);
      volumeSeriesRef.current = null;
    }

    // Map data to lightweight-charts format
    const mapped = data.map((d) => ({
      time: d.date.split("T")[0] as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
      volume: d.volume,
    }));

    // Determine color based on overall trend
    const upColor = "#34d399";
    const downColor = "#f87171";

    if (mode === "candle") {
      const series = chart.addSeries(CandlestickSeries, {
        upColor,
        downColor,
        borderUpColor: upColor,
        borderDownColor: downColor,
        wickUpColor: upColor,
        wickDownColor: downColor,
      });
      series.setData(mapped as CandlestickData<Time>[]);
      candleSeriesRef.current = series;
    } else {
      const trendColor = isPositive ? upColor : downColor;
      const series = chart.addSeries(LineSeries, {
        color: trendColor,
        lineWidth: 2,
        crosshairMarkerRadius: 5,
        crosshairMarkerBorderColor: "#0c0c14",
        crosshairMarkerBorderWidth: 2,
      });
      series.setData(
        mapped.map((d) => ({ time: d.time, value: d.close })),
      );
      lineSeriesRef.current = series;
    }

    // Volume histogram
    const volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    const volData: HistogramData<Time>[] = mapped.map((d) => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open ? "rgba(52, 211, 153, 0.25)" : "rgba(248, 113, 113, 0.25)",
    }));
    volSeries.setData(volData);
    volumeSeriesRef.current = volSeries;

    chart.timeScale().fitContent();
  }, [data, mode, isPositive]);

  useEffect(() => {
    updateSeries();
  }, [updateSeries]);

  return (
    <div style={{ background: "var(--color-surface-0)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "var(--space-md) var(--space-lg)",
          minHeight: 44,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-sm)" }}>
          <span
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Price
          </span>
          {!loading && prices.length > 0 && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "var(--text-sm)",
                fontWeight: 700,
                color: isPositive ? "var(--color-success)" : "var(--color-error)",
              }}
            >
              {isPositive ? "+" : ""}
              {changePct.toFixed(2)}%
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: "var(--space-xs)", alignItems: "center" }}>
          {/* Mode toggle */}
          <div style={{ display: "flex", gap: 2, marginRight: "var(--space-sm)" }}>
            {(["candle", "line"] as ChartMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  padding: "4px 8px",
                  fontSize: 10,
                  fontWeight: mode === m ? 700 : 500,
                  fontFamily: "var(--font-mono)",
                  background: mode === m ? "var(--color-accent-ghost)" : "transparent",
                  color: mode === m ? "var(--color-accent-bright)" : "var(--color-text-muted)",
                  border: "none",
                  borderRadius: "var(--radius-full)",
                  cursor: "pointer",
                  transition: "all var(--duration-fast) var(--ease-out)",
                  textTransform: "uppercase",
                }}
              >
                {m === "candle" ? "OHLC" : "Line"}
              </button>
            ))}
          </div>

          {/* Period selector */}
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
        <div ref={containerRef} style={{ height: 300 }} />
        {loading && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 var(--space-lg) var(--space-md)" }}>
            <div className="skeleton" style={{ width: "100%", height: 260, borderRadius: "var(--radius-sm)" }} />
          </div>
        )}
        {!loading && data.length < 2 && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>No data</span>
          </div>
        )}
      </div>
    </div>
  );
}
