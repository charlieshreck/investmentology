import { useEffect, useRef, useState } from "react";

interface StreamTextProps {
  text: string;
  speed?: number; // ms per character, default 8
  style?: React.CSSProperties;
}

/**
 * Types out text progressively when mounted.
 * Uses direct DOM mutation — no re-render per character.
 * Only animates on first mount; if text changes, shows instantly.
 */
export function StreamText({ text, speed = 8, style }: StreamTextProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const cursorRef = useRef<HTMLSpanElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!ref.current || !text) return;

    // Only animate on first mount
    if (hasAnimated.current) {
      ref.current.textContent = text;
      if (cursorRef.current) cursorRef.current.style.display = "none";
      return;
    }

    hasAnimated.current = true;
    ref.current.textContent = "";
    if (cursorRef.current) cursorRef.current.style.display = "inline-block";

    let i = 0;
    let timer: ReturnType<typeof setTimeout>;

    const tick = () => {
      if (!ref.current) return;
      const chunkSize = Math.max(1, Math.floor(16 / speed));
      const end = Math.min(i + chunkSize, text.length);
      ref.current.textContent = text.slice(0, end);
      i = end;
      if (i < text.length) {
        timer = setTimeout(tick, speed * chunkSize);
      } else if (cursorRef.current) {
        cursorRef.current.style.display = "none";
      }
    };

    timer = setTimeout(tick, 60);
    return () => clearTimeout(timer);
  }, [text, speed]);

  return (
    <span style={style}>
      <span ref={ref} />
      <span
        ref={cursorRef}
        style={{
          display: "none",
          width: 1.5,
          height: "1em",
          background: "var(--color-accent-bright)",
          marginLeft: 1,
          verticalAlign: "text-bottom",
          animation: "pulse-glow 1s ease-in-out infinite",
        }}
      />
    </span>
  );
}
