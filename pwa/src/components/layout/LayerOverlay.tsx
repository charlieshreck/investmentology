import { useEffect, useRef, type ReactNode } from "react";

interface LayerOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function LayerOverlay({
  isOpen,
  onClose,
  title,
  children,
}: LayerOverlayProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const startY = useRef(0);
  const wasAtTop = useRef(false);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  // Only allow swipe-to-close when content is scrolled to the top
  const handleTouchStart = (e: React.TouchEvent) => {
    startY.current = e.touches[0].clientY;
    wasAtTop.current = (contentRef.current?.scrollTop ?? 0) <= 0;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!wasAtTop.current) return;
    const deltaY = e.changedTouches[0].clientY - startY.current;
    if (deltaY > 120) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          background: "rgba(0, 0, 0, 0.6)",
          backdropFilter: "blur(4px)",
        }}
      />

      {/* Panel */}
      <div
        ref={contentRef}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        style={{
          position: "relative",
          background: "var(--glass-bg-elevated)",
          backdropFilter: `blur(${`var(--glass-blur)`})`,
          WebkitBackdropFilter: `blur(var(--glass-blur))`,
          borderTop: "1px solid var(--glass-border)",
          borderRadius: "var(--radius-xl) var(--radius-xl) 0 0",
          maxHeight: "90vh",
          overflowY: "auto",
          WebkitOverflowScrolling: "touch",
          animation: "slideUp var(--duration-normal) var(--ease-out)",
          paddingBottom: "calc(var(--safe-bottom) + var(--nav-height))",
        }}
      >
        {/* Drag handle */}
        <div
          style={{
            position: "sticky",
            top: 0,
            zIndex: 10,
            background: "var(--glass-bg-elevated)",
            backdropFilter: `blur(var(--glass-blur))`,
            WebkitBackdropFilter: `blur(var(--glass-blur))`,
            borderBottom: "1px solid var(--glass-border)",
            borderRadius: "var(--radius-xl) var(--radius-xl) 0 0",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              padding: "var(--space-md) 0",
            }}
          >
            <div
              style={{
                width: 36,
                height: 4,
                borderRadius: "var(--radius-full)",
                background: "var(--color-surface-3)",
              }}
            />
          </div>

          {/* Header */}
          <div
            style={{
              padding: "0 var(--space-xl) var(--space-lg)",
            }}
          >
            <h2
              style={{
                margin: 0,
                fontSize: "var(--text-lg)",
                fontWeight: 600,
              }}
            >
              {title}
            </h2>
          </div>
        </div>

        {/* Content */}
        <div style={{ padding: "var(--space-xl)" }}>{children}</div>
      </div>

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
