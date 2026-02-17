import { useCallback, useRef } from "react";
import confetti from "canvas-confetti";

type ConfettiType = "profit" | "milestone" | "streak";

const prefersReducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useConfetti() {
  // Track which tickers already celebrated so we don't repeat per session
  const celebrated = useRef(new Set<string>());

  const fire = useCallback((type: ConfettiType, key?: string) => {
    if (prefersReducedMotion()) return;
    if (key && celebrated.current.has(key)) return;
    if (key) celebrated.current.add(key);

    switch (type) {
      case "profit":
        // Gold coins burst
        confetti({
          particleCount: 60,
          spread: 55,
          origin: { y: 0.7 },
          colors: ["#FFD700", "#FFA500", "#DAA520"],
          scalar: 1.1,
        });
        break;

      case "milestone":
        // Rainbow spread
        confetti({
          particleCount: 100,
          spread: 100,
          origin: { y: 0.6 },
          colors: ["#ff0000", "#ff7700", "#ffdd00", "#00ff00", "#0077ff", "#8800ff"],
        });
        break;

      case "streak":
        // Fireworks — two bursts
        confetti({
          particleCount: 40,
          angle: 60,
          spread: 45,
          origin: { x: 0.1, y: 0.6 },
        });
        confetti({
          particleCount: 40,
          angle: 120,
          spread: 45,
          origin: { x: 0.9, y: 0.6 },
        });
        break;
    }
  }, []);

  return { fire, celebrated: celebrated.current };
}
