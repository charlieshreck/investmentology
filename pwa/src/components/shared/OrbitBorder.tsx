import { useRef, useState, useEffect, type ReactNode } from "react";
import { motion } from "framer-motion";

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

function roundedRectPath(w: number, h: number, r: number): { d: string; length: number } {
  const cr = Math.min(r, w / 2, h / 2);
  const straight = 2 * (w - 2 * cr) + 2 * (h - 2 * cr);
  const corners = 2 * Math.PI * cr;
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

/** Animated orbiting dot layer */
function OrbitPath({
  d,
  perimeter,
  dotLen,
  color,
  width,
  duration,
  reverse,
  filter,
  opacity = 1,
}: {
  d: string;
  perimeter: number;
  dotLen: number;
  color: string;
  width: number;
  duration: number;
  reverse: boolean;
  filter?: string;
  opacity?: number;
}) {
  const from = reverse ? 0 : perimeter;
  const to = reverse ? perimeter : 0;

  return (
    <motion.path
      d={d}
      fill="none"
      stroke={color}
      strokeWidth={width}
      strokeLinecap="round"
      strokeDasharray={`${dotLen} ${perimeter - dotLen}`}
      filter={filter}
      opacity={opacity}
      animate={{ strokeDashoffset: [from, to] }}
      transition={{
        strokeDashoffset: {
          duration,
          ease: "linear",
          repeat: Infinity,
        },
      }}
    />
  );
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
  const filterId = `glow-${verdict}-${size?.w ?? 0}`;
  const filterOuterId = `glow-outer-${verdict}-${size?.w ?? 0}`;

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        borderRadius: radius,
        border: `1px solid ${config.color}40`,
        boxShadow: `0 0 20px ${config.color}15, 0 0 60px ${config.color}08, inset 0 0 20px ${config.color}06`,
      }}
    >
      {children}

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
            <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3" />
            </filter>
            <filter id={filterOuterId} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="8" />
            </filter>
          </defs>

          {/* Static glowing border frame */}
          <path
            d={pathData.d}
            fill="none"
            stroke={config.color}
            strokeWidth={1}
            opacity={0.25}
          />

          {/* Outer glow trail */}
          <OrbitPath
            d={pathData.d}
            perimeter={pathData.length}
            dotLen={dotLen}
            color={config.color}
            width={strokeWidth + 4}
            duration={config.duration}
            reverse={config.reverse}
            filter={`url(#${filterOuterId})`}
            opacity={0.3}
          />

          {/* Inner glow halo */}
          <OrbitPath
            d={pathData.d}
            perimeter={pathData.length}
            dotLen={dotLen}
            color={config.color}
            width={strokeWidth + 2}
            duration={config.duration}
            reverse={config.reverse}
            filter={`url(#${filterId})`}
            opacity={0.5}
          />

          {/* Core dot */}
          <OrbitPath
            d={pathData.d}
            perimeter={pathData.length}
            dotLen={dotLen}
            color={config.color}
            width={strokeWidth}
            duration={config.duration}
            reverse={config.reverse}
          />
        </svg>
      )}
    </div>
  );
}
