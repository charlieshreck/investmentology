import { useRef, useCallback, useState, useEffect } from "react";

interface PullToRefreshOptions {
  onRefresh: () => Promise<void> | void;
  threshold?: number;    // px to pull before triggering (default 80)
  maxPull?: number;      // max visual displacement (default 120)
}

interface PullToRefreshResult {
  /** Attach to the scrollable container */
  containerRef: React.RefObject<HTMLDivElement | null>;
  /** Pull distance 0..maxPull for indicator rendering */
  pullDistance: number;
  /** Whether a refresh is currently in progress */
  refreshing: boolean;
}

/**
 * Touch-based pull-to-refresh for mobile PWA.
 * Only activates when scrollTop === 0 and finger drags downward.
 */
export function usePullToRefresh({
  onRefresh,
  threshold = 80,
  maxPull = 120,
}: PullToRefreshOptions): PullToRefreshResult {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [pullDistance, setPullDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef(0);
  const pulling = useRef(false);
  const currentPull = useRef(0); // ref mirror of pullDistance for closure access

  const handleTouchStart = useCallback((e: TouchEvent) => {
    const el = containerRef.current;
    if (!el || el.scrollTop > 0 || refreshing) return;
    startY.current = e.touches[0].clientY;
    pulling.current = true;
  }, [refreshing]);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!pulling.current) return;
    const delta = e.touches[0].clientY - startY.current;
    if (delta < 0) { pulling.current = false; currentPull.current = 0; setPullDistance(0); return; }
    const dampened = Math.min(delta * 0.4, maxPull);
    currentPull.current = dampened;
    setPullDistance(dampened);
  }, [maxPull]);

  const handleTouchEnd = useCallback(async () => {
    if (!pulling.current) return;
    pulling.current = false;
    const dist = currentPull.current;
    if (dist >= threshold) {
      setRefreshing(true);
      currentPull.current = threshold * 0.5;
      setPullDistance(threshold * 0.5);
      try {
        await onRefresh();
      } finally {
        setRefreshing(false);
        currentPull.current = 0;
        setPullDistance(0);
      }
    } else {
      currentPull.current = 0;
      setPullDistance(0);
    }
  }, [threshold, onRefresh]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener("touchstart", handleTouchStart, { passive: true });
    el.addEventListener("touchmove", handleTouchMove, { passive: true });
    el.addEventListener("touchend", handleTouchEnd);
    return () => {
      el.removeEventListener("touchstart", handleTouchStart);
      el.removeEventListener("touchmove", handleTouchMove);
      el.removeEventListener("touchend", handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd]);

  return { containerRef, pullDistance, refreshing };
}
