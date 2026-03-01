import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { BottomNav } from "./components/layout/BottomNav";
import { LayerOverlay } from "./components/layout/LayerOverlay";
import { PageTransition } from "./components/layout/PageTransition";
import { Portfolio } from "./views/Portfolio";
import { QuantGate } from "./views/QuantGate";
import { Watchlist } from "./views/Watchlist";
import { Decisions } from "./views/Decisions";
import { Analyse } from "./views/Analyse";
import { Learning } from "./views/Learning";
import { SystemHealth } from "./views/SystemHealth";
import { Agents } from "./views/Agents";
import { Recommendations } from "./views/Recommendations";
import { Backtest } from "./views/Backtest";
import { SettingsView } from "./views/SettingsView";
import { StockDeepDive } from "./views/StockDeepDive";
import { Login } from "./views/Login";
import { useAuth } from "./hooks/useAuth";
import { useStore } from "./stores/useStore";
import { AnalysisStatusBar } from "./components/shared/AnalysisStatusBar";
import { CommandPalette } from "./components/shared/CommandPalette";
import { AnalysisProvider } from "./contexts/AnalysisContext";
import "./stores/useThemeStore"; // Initialize theme on load

// Intercept all fetch calls — on 401 force reload to show login
const originalFetch = window.fetch;
window.fetch = async (...args) => {
  const res = await originalFetch(...args);
  if (res.status === 401) {
    const url = typeof args[0] === "string" ? args[0] : (args[0] as Request).url;
    // Don't intercept auth endpoints themselves
    if (!url.includes("/auth/")) {
      window.location.reload();
    }
  }
  return res;
};

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
    <BrowserRouter>
      <AnalysisProvider>
        <AppShell offline={offline} />
      </AnalysisProvider>
    </BrowserRouter>
  );
}

function AppShell({ offline }: { offline: boolean }) {
  const location = useLocation();
  const overlayTicker = useStore((s) => s.overlayTicker);
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {offline && (
        <div
          style={{
            background: "var(--color-warning, #f59e0b)",
            color: "#000",
            textAlign: "center",
            padding: "6px",
            fontSize: "12px",
            fontWeight: 600,
            zIndex: 100,
          }}
        >
          Offline — showing cached data
        </div>
      )}
      <AnalysisStatusBar />
      <div
        style={{
          flex: 1,
          overflow: "hidden",
          maxWidth: "520px",
          width: "100%",
          margin: "0 auto",
        }}
      >
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<PageTransition><Portfolio /></PageTransition>} />
            <Route path="/screener" element={<PageTransition><QuantGate /></PageTransition>} />
            <Route path="/watchlist" element={<PageTransition><Watchlist /></PageTransition>} />
            <Route path="/log" element={<PageTransition><Decisions /></PageTransition>} />
            <Route path="/analyze" element={<PageTransition><Analyse /></PageTransition>} />
            <Route path="/learning" element={<PageTransition><Learning /></PageTransition>} />
            <Route path="/recommendations" element={<PageTransition><Recommendations /></PageTransition>} />
            <Route path="/agents" element={<PageTransition><Agents /></PageTransition>} />
            <Route path="/backtest" element={<PageTransition><Backtest /></PageTransition>} />
            <Route path="/health" element={<PageTransition><SystemHealth /></PageTransition>} />
            <Route path="/settings" element={<PageTransition><SettingsView /></PageTransition>} />
          </Routes>
        </AnimatePresence>
      </div>
      <BottomNav />

      {/* Command palette (Cmd+K) */}
      <CommandPalette />

      {/* Stock deep-dive overlay */}
      <LayerOverlay
        isOpen={overlayTicker !== null}
        onClose={() => setOverlayTicker(null)}
        title={overlayTicker ?? ""}
      >
        {overlayTicker && <StockDeepDive ticker={overlayTicker} />}
      </LayerOverlay>
    </div>
  );
}
