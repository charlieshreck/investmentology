import { useEffect, useRef } from "react";
import { animate } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  format: (n: number) => string;
  className?: string;
  style?: React.CSSProperties;
  duration?: number;
}

export function AnimatedNumber({
  value,
  format,
  className,
  style,
  duration = 0.6,
}: AnimatedNumberProps) {
  const nodeRef = useRef<HTMLSpanElement>(null);
  const prevValue = useRef(value);
  const initialized = useRef(false);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) return;

    // Skip animation on first render
    if (!initialized.current) {
      initialized.current = true;
      node.textContent = format(value);
      prevValue.current = value;
      return;
    }

    // Don't animate if value hasn't changed
    if (prevValue.current === value) return;

    const controls = animate(prevValue.current, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        node.textContent = format(v);
      },
    });
    prevValue.current = value;
    return () => controls.stop();
  }, [value, format, duration]);

  return (
    <span ref={nodeRef} className={`tabular-nums ${className ?? ""}`} style={style}>
      {format(value)}
    </span>
  );
}
