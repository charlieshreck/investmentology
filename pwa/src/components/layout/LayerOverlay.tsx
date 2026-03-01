import { useEffect, type ReactNode } from "react";
import { motion, AnimatePresence, useMotionValue, useTransform } from "framer-motion";

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
  const y = useMotionValue(0);
  const backdropOpacity = useTransform(y, [0, 300], [0.6, 0]);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
      y.set(0);
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen, y]);

  return (
    <AnimatePresence>
      {isOpen && (
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
          <motion.div
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{
              position: "absolute",
              inset: 0,
              backdropFilter: "blur(4px)",
              WebkitBackdropFilter: "blur(4px)",
              backgroundColor: `rgba(0, 0, 0, 0.6)`,
              opacity: backdropOpacity,
            }}
          />

          {/* Panel */}
          <motion.div
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={{ top: 0.05, bottom: 0.3 }}
            onDragEnd={(_e, info) => {
              if (info.offset.y > 100 || info.velocity.y > 500) {
                onClose();
              }
            }}
            style={{
              y,
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
            }}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
          >
            {/* Drag handle */}
            <div
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

            {/* Scrollable content */}
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
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
