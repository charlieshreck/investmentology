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
  const startY = useRef(0);

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

  // Swipe-to-close ONLY on drag handle area
  const handleTouchStart = (e: React.TouchEvent) => {
    startY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    const deltaY = e.changedTouches[0].clientY - startY.current;
    if (deltaY > 80) {
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

      {/* Panel — full height minus safe area, scrolls independently */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          top: "5vh",
          display: "flex",
          flexDirection: "column",
          background: "var(--glass-bg-elevated)",
          backdropFilter: `blur(var(--glass-blur))`,
          WebkitBackdropFilter: `blur(var(--glass-blur))`,
          borderTop: "1px solid var(--glass-border)",
          borderRadius: "var(--radius-xl) var(--radius-xl) 0 0",
          animation: "slideUp var(--duration-normal) var(--ease-out)",
        }}
      >
        {/* Drag handle — ONLY this area triggers swipe-to-close */}
        <div
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
          style={{
            flexShrink: 0,
            cursor: "grab",
            touchAction: "none",
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
              borderBottom: "1px solid var(--glass-border)",
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

        {/* Scrollable content — independent scroll, no touch interference */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            overflowX: "hidden",
            WebkitOverflowScrolling: "touch",
            padding: "var(--space-xl)",
            paddingBottom: "calc(var(--safe-bottom) + var(--nav-height) + var(--space-xl))",
          }}
        >
          {children}
        </div>
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
