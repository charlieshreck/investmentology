import { lazy, Suspense, useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { BottomNav } from "./components/layout/BottomNav";
import { LayerOverlay } from "./components/layout/LayerOverlay";
import { PageTransition } from "./components/layout/PageTransition";
import { AppErrorBoundary, ViewErrorBoundary, OverlayErrorBoundary } from "./components/shared/ErrorBoundary";
import { Today } from "./views/Today"; // Landing page — keep static for instant paint
import { Login } from "./views/Login";
import { useAuth } from "./hooks/useAuth";
import { useIsDesktop } from "./hooks/useMediaQuery";
import { useStore } from "./stores/useStore";
import { AnalysisStatusBar } from "./components/shared/AnalysisStatusBar";
import { CommandPalette } from "./components/shared/CommandPalette";
import { AnalysisProvider } from "./contexts/AnalysisContext";
import { queryClient } from "./utils/apiClient";
import "./stores/useThemeStore"; // Initialize theme on load

// Lazy-loaded views (all named exports → wrap in default)
const Portfolio = lazy(() => import("./views/Portfolio").then(m => ({ default: m.Portfolio })));
const QuantGate = lazy(() => import("./views/QuantGate").then(m => ({ default: m.QuantGate })));
const Watchlist = lazy(() => import("./views/Watchlist").then(m => ({ default: m.Watchlist })));
const Decisions = lazy(() => import("./views/Decisions").then(m => ({ default: m.Decisions })));
const Analyse = lazy(() => import("./views/Analyse").then(m => ({ default: m.Analyse })));
const Learning = lazy(() => import("./views/Learning").then(m => ({ default: m.Learning })));
const SystemHealth = lazy(() => import("./views/SystemHealth").then(m => ({ default: m.SystemHealth })));
const Agents = lazy(() => import("./views/Agents").then(m => ({ default: m.Agents })));
const Pipeline = lazy(() => import("./views/Pipeline").then(m => ({ default: m.Pipeline })));
const Recommendations = lazy(() => import("./views/Recommendations").then(m => ({ default: m.Recommendations })));
const Backtest = lazy(() => import("./views/Backtest").then(m => ({ default: m.Backtest })));
const SettingsView = lazy(() => import("./views/SettingsView").then(m => ({ default: m.SettingsView })));
const StockDeepDive = lazy(() => import("./views/StockDeepDive").then(m => ({ default: m.StockDeepDive })));

function ViewLoader() {
  return (
    <div style={{
      height: "100%", display: "flex", alignItems: "center",
      justifyContent: "center", color: "var(--color-text-muted)",
      fontSize: "var(--text-sm)",
    }}>
      Loading...
    </div>
  );
}

export default function App() {
  const { isAuthenticated, error, login, logout } = useAuth();
  const [offline, setOffline] = useState(!navigator.onLine);

  // Store logout in window for use by nav/settings
  useEffect(() => {
    (window as any).__logout = logout;
  }, [logout]);

  // Offline detection
  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => setOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  // Still checking auth state
  if (isAuthenticated === null) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--color-base)",
          color: "var(--color-text-muted)",
          fontSize: "var(--text-sm)",
        }}
      >
        Loading...
      </div>
    );
  }

  // Not authenticated — show login
  if (!isAuthenticated) {
    return <Login onLogin={login} error={error} />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>
        <BrowserRouter>
          <AnalysisProvider>
            <AppShell offline={offline} />
          </AnalysisProvider>
        </BrowserRouter>
      </AppErrorBoundary>
    </QueryClientProvider>
  );
}

function AppShell({ offline }: { offline: boolean }) {
  const location = useLocation();
  const overlayTicker = useStore((s) => s.overlayTicker);
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);
  const isDesktop = useIsDesktop();

  // Keep last ticker visible during close animation to prevent blank flash
  const [lastOverlayTicker, setLastOverlayTicker] = useState<string | null>(null);
  useEffect(() => {
    if (overlayTicker !== null) setLastOverlayTicker(overlayTicker);
  }, [overlayTicker]);

  return (
    <div style={{
      height: "100%",
      display: "flex",
      flexDirection: "column",
      marginLeft: isDesktop ? "var(--sidebar-width)" : undefined,
    }}>
      <AnimatePresence>
        {offline && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: "hidden", zIndex: 100, flexShrink: 0 }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                padding: "5px 12px",
                background: "rgba(251, 191, 36, 0.12)",
                borderBottom: "1px solid rgba(251, 191, 36, 0.2)",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--color-warning)",
                letterSpacing: "0.02em",
              }}
            >
              <span style={{
                width: 6, height: 6, borderRadius: "50%",
                background: "var(--color-warning)",
                animation: "pulse-glow 2s ease-in-out infinite",
              }} />
              Offline — showing cached data
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <AnalysisStatusBar />
      <div
        style={{
          flex: 1,
          overflow: "hidden",
          maxWidth: isDesktop ? "1200px" : "520px",
          width: "100%",
          margin: "0 auto",
        }}
      >
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<PageTransition><Today /></PageTransition>} />
            <Route path="/portfolio" element={<ViewErrorBoundary viewName="Portfolio"><Suspense fallback={<ViewLoader />}><PageTransition><Portfolio /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/screener" element={<ViewErrorBoundary viewName="Screener"><Suspense fallback={<ViewLoader />}><PageTransition><QuantGate /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/watchlist" element={<ViewErrorBoundary viewName="Watchlist"><Suspense fallback={<ViewLoader />}><PageTransition><Watchlist /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/log" element={<ViewErrorBoundary viewName="Decisions"><Suspense fallback={<ViewLoader />}><PageTransition><Decisions /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/analyze" element={<ViewErrorBoundary viewName="Analyse"><Suspense fallback={<ViewLoader />}><PageTransition><Analyse /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/learning" element={<ViewErrorBoundary viewName="Learning"><Suspense fallback={<ViewLoader />}><PageTransition><Learning /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/recommendations" element={<ViewErrorBoundary viewName="Recommendations"><Suspense fallback={<ViewLoader />}><PageTransition><Recommendations /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/agents" element={<ViewErrorBoundary viewName="Agents"><Suspense fallback={<ViewLoader />}><PageTransition><Agents /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/pipeline" element={<ViewErrorBoundary viewName="Pipeline"><Suspense fallback={<ViewLoader />}><PageTransition><Pipeline /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/backtest" element={<ViewErrorBoundary viewName="Backtest"><Suspense fallback={<ViewLoader />}><PageTransition><Backtest /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/health" element={<ViewErrorBoundary viewName="System Health"><Suspense fallback={<ViewLoader />}><PageTransition><SystemHealth /></PageTransition></Suspense></ViewErrorBoundary>} />
            <Route path="/settings" element={<ViewErrorBoundary viewName="Settings"><Suspense fallback={<ViewLoader />}><PageTransition><SettingsView /></PageTransition></Suspense></ViewErrorBoundary>} />
          </Routes>
        </AnimatePresence>
      </div>
      <BottomNav />

      {/* Command palette (Cmd+K) */}
      <CommandPalette />

      {/* Stock deep-dive overlay */}
      {/* Use overlayTicker when open, fall back to lastOverlayTicker during close animation */}
      <LayerOverlay
        isOpen={overlayTicker !== null}
        onClose={() => setOverlayTicker(null)}
        title={overlayTicker ?? lastOverlayTicker ?? ""}
      >
        <OverlayErrorBoundary onClose={() => setOverlayTicker(null)}>
          <Suspense fallback={<ViewLoader />}>
            {(overlayTicker ?? lastOverlayTicker) != null && (
              <StockDeepDive ticker={(overlayTicker ?? lastOverlayTicker)!} />
            )}
          </Suspense>
        </OverlayErrorBoundary>
      </LayerOverlay>
    </div>
  );
}
