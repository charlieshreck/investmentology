import { useRef, useEffect, useState } from "react";
import type { Correlation } from "../../hooks/useCorrelations";

interface Props {
  tickers: string[];
  correlations: Correlation[];
}

function corrColor(v: number): string {
  // -1 (red) → 0 (neutral) → +1 (green)
  if (v >= 0) {
    const g = Math.round(80 + v * 140);
    return `rgba(52, ${g}, 100, ${0.3 + v * 0.6})`;
  }
  const r = Math.round(80 + Math.abs(v) * 140);
  return `rgba(${r}, 60, 70, ${0.3 + Math.abs(v) * 0.6})`;
}

export function CorrelationHeatmap({ tickers, correlations }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);

  // Build lookup map
  const corrMap = new Map<string, number>();
  for (const c of correlations) {
    corrMap.set(`${c.ticker1}:${c.ticker2}`, c.value);
    corrMap.set(`${c.ticker2}:${c.ticker1}`, c.value);
  }

  const n = tickers.length;
  const LABEL_WIDTH = 52;
  const CELL_SIZE = Math.max(24, Math.min(40, Math.floor((300 - LABEL_WIDTH) / n)));
  const width = LABEL_WIDTH + n * CELL_SIZE;
  const height = LABEL_WIDTH + n * CELL_SIZE;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    // Draw column labels (top)
    ctx.font = "10px var(--font-mono, monospace)";
    ctx.fillStyle = "rgba(255,255,255,0.6)";
    ctx.textAlign = "center";
    for (let j = 0; j < n; j++) {
      ctx.save();
      const x = LABEL_WIDTH + j * CELL_SIZE + CELL_SIZE / 2;
      const y = LABEL_WIDTH - 4;
      ctx.translate(x, y);
      ctx.rotate(-Math.PI / 4);
      ctx.fillText(tickers[j], 0, 0);
      ctx.restore();
    }

    // Draw row labels (left)
    ctx.textAlign = "right";
    for (let i = 0; i < n; i++) {
      ctx.fillStyle = "rgba(255,255,255,0.6)";
      ctx.fillText(tickers[i], LABEL_WIDTH - 6, LABEL_WIDTH + i * CELL_SIZE + CELL_SIZE / 2 + 3);
    }

    // Draw cells
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const x = LABEL_WIDTH + j * CELL_SIZE;
        const y = LABEL_WIDTH + i * CELL_SIZE;

        let val: number;
        if (i === j) {
          val = 1.0;
        } else {
          const key = `${tickers[i]}:${tickers[j]}`;
          val = corrMap.get(key) ?? 0;
        }

        ctx.fillStyle = corrColor(val);
        ctx.fillRect(x + 1, y + 1, CELL_SIZE - 2, CELL_SIZE - 2);

        // Show value text only if cells are large enough
        if (CELL_SIZE >= 32) {
          ctx.fillStyle = "rgba(255,255,255,0.8)";
          ctx.textAlign = "center";
          ctx.font = "9px var(--font-mono, monospace)";
          ctx.fillText(val.toFixed(2), x + CELL_SIZE / 2, y + CELL_SIZE / 2 + 3);
        }
      }
    }
  }, [tickers, correlations, corrMap, n, width, height]);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const col = Math.floor((mx - LABEL_WIDTH) / CELL_SIZE);
    const row = Math.floor((my - LABEL_WIDTH) / CELL_SIZE);

    if (col >= 0 && col < n && row >= 0 && row < n) {
      let val: number;
      if (row === col) {
        val = 1.0;
      } else {
        val = corrMap.get(`${tickers[row]}:${tickers[col]}`) ?? 0;
      }
      setTooltip({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top - 30,
        text: `${tickers[row]} / ${tickers[col]}: ${val.toFixed(3)}`,
      });
    } else {
      setTooltip(null);
    }
  };

  return (
    <div ref={containerRef} style={{ position: "relative", overflowX: "auto" }}>
      <canvas
        ref={canvasRef}
        style={{ width, height, cursor: "crosshair" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      />
      {tooltip && (
        <div
          style={{
            position: "absolute",
            left: tooltip.x,
            top: tooltip.y,
            background: "var(--color-surface-2, #1a1a2e)",
            color: "var(--color-text, #fff)",
            fontSize: "11px",
            fontFamily: "var(--font-mono, monospace)",
            padding: "4px 8px",
            borderRadius: "4px",
            pointerEvents: "none",
            whiteSpace: "nowrap",
            border: "1px solid var(--glass-border, rgba(255,255,255,0.1))",
            transform: "translateX(-50%)",
          }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  );
}
