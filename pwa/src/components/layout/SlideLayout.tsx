import { useRef, type ReactNode } from "react";

interface SlideLayoutProps {
  children: ReactNode;
  activeIndex: number;
  onSlideChange?: (index: number) => void;
}

export function SlideLayout({
  children,
  activeIndex,
  onSlideChange,
}: SlideLayoutProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el || !onSlideChange) return;
    const index = Math.round(el.scrollLeft / el.clientWidth);
    onSlideChange(index);
  };

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{
        display: "flex",
        overflowX: "auto",
        scrollSnapType: "x mandatory",
        WebkitOverflowScrolling: "touch",
        height: `calc(100% - var(--nav-height) - var(--safe-bottom))`,
        scrollbarWidth: "none",
      }}
    >
      {Array.isArray(children)
        ? children.map((child, i) => (
            <div
              key={i}
              style={{
                flex: "0 0 100%",
                width: "100%",
                height: "100%",
                scrollSnapAlign: "start",
                overflowY: "auto",
                transform:
                  i === activeIndex ? "none" : "translateZ(0)",
              }}
            >
              {child}
            </div>
          ))
        : children}
    </div>
  );
}
