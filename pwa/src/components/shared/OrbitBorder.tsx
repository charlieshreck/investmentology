import { useRef, useState, useEffect, type ReactNode } from "react";

/**
 * Verdict → orbiting dot parameters.
 * Speed encodes urgency, direction encodes buy/sell, color encodes sentiment.
 */
const VERDICT_CONFIG: Record<string, { color: string; duration: number; reverse: boolean }> = {
  STRONG_BUY:  { color: "#34d399", duration: 2,  reverse: false },
  BUY:         { color: "#34d399", duration: 3,  reverse: false },
  ACCUMULATE:  { color: "rgba(52,211,153,0.7)", duration: 4, reverse: false },
  WATCHLIST:   { color: "#a78bfa", duration: 8,  reverse: false },
  HOLD:        { color: "#fbbf24", duration: 6,  reverse: false },
  REDUCE:      { color: "#f87171", duration: 4,  reverse: true },
  SELL:        { color: "#f87171", duration: 3,  reverse: true },
  STRONG_SELL: { color: "#f87171", duration: 2,  reverse: true },
};

const DEFAULT_CONFIG = { color: "#a78bfa", duration: 8, reverse: false };

/**
 * Draws a rounded-rect SVG path for the given dimensions and radius.
 * Returns the path `d` string and its total length.
 */
function roundedRectPath(w: number, h: number, r: number): { d: string; length: number } {
  // Clamp radius to half of smallest dimension
  const cr = Math.min(r, w / 2, h / 2);
  const straight = 2 * (w - 2 * cr) + 2 * (h - 2 * cr);
  const corners = 2 * Math.PI * cr; // 4 quarter-arcs ≈ full circle
  const length = straight + corners;

  const d = [
    `M ${cr} 0`,
    `L ${w - cr} 0`,
    `A ${cr} ${cr} 0 0 1 ${w} ${cr}`,
    `L ${w} ${h - cr}`,
    `A ${cr} ${cr} 0 0 1 ${w - cr} ${h}`,
    `L ${cr} ${h}`,
    `A ${cr} ${cr} 0 0 1 0 ${h - cr}`,
    `L 0 ${cr}`,
    `A ${cr} ${cr} 0 0 1 ${cr} 0`,
    "Z",
  ].join(" ");

  return { d, length };
}

export function OrbitBorder({
  verdict,
  radius = 18,
  strokeWidth = 2,
  children,
}: {
  verdict: string;
  radius?: number;
  strokeWidth?: number;
  children: ReactNode;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const update = () => {
      setSize({ w: el.offsetWidth, h: el.offsetHeight });
    };
    update();

    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const config = VERDICT_CONFIG[verdict] ?? DEFAULT_CONFIG;

  let pathData: { d: string; length: number } | null = null;
  if (size && size.w > 0 && size.h > 0) {
    pathData = roundedRectPath(size.w, size.h, radius);
  }

  const dotLen = 14;

  return (
    <div
      ref={containerRef}
      style={{ position: "relative" }}
    >
      {children}

      {/* SVG overlay — orbiting dot */}
      {pathData && (
        <svg
          width={size!.w}
          height={size!.h}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            pointerEvents: "none",
            zIndex: 1,
            overflow: "visible",
          }}
        >
          <defs>
            <filter id={`glow-${verdict}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3" />
            </filter>
            <filter id={`glow-outer-${verdict}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="8" />
            </filter>
          </defs>

          {/* Outer glow trail */}
          <path
            d={pathData.d}
            fill="none"
            stroke={config.color}
            strokeWidth={strokeWidth + 4}
            strokeLinecap="round"
            strokeDasharray={`${dotLen} ${pathData.length - dotLen}`}
            filter={`url(#glow-outer-${verdict})`}
            opacity={0.3}
            style={{
              ["--perimeter" as string]: pathData.length,
              animation: `orbit-dot ${config.duration}s linear infinite${config.reverse ? " reverse" : ""}`,
            } as React.CSSProperties}
          />

          {/* Inner glow halo */}
          <path
            d={pathData.d}
            fill="none"
            stroke={config.color}
            strokeWidth={strokeWidth + 2}
            strokeLinecap="round"
            strokeDasharray={`${dotLen} ${pathData.length - dotLen}`}
            filter={`url(#glow-${verdict})`}
            opacity={0.5}
            style={{
              ["--perimeter" as string]: pathData.length,
              animation: `orbit-dot ${config.duration}s linear infinite${config.reverse ? " reverse" : ""}`,
            } as React.CSSProperties}
          />

          {/* Core dot */}
          <path
            d={pathData.d}
            fill="none"
            stroke={config.color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${dotLen} ${pathData.length - dotLen}`}
            style={{
              ["--perimeter" as string]: pathData.length,
              animation: `orbit-dot ${config.duration}s linear infinite${config.reverse ? " reverse" : ""}`,
            } as React.CSSProperties}
          />
        </svg>
      )}
    </div>
  );
}
