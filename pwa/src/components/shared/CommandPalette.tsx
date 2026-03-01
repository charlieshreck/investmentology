import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, Search, Star, Lightbulb, Plus,
  BookOpen, Activity, Bot, TrendingUp, Heart, Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useStore } from "../../stores/useStore";

interface CommandItem {
  id: string;
  label: string;
  icon: LucideIcon;
  action: () => void;
  category: "nav" | "recent" | "watchlist";
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const recentAnalyses = useStore((s) => s.recentAnalyses);
  const setOverlayTicker = useStore((s) => s.setOverlayTicker);

  // Cmd+K / Ctrl+K to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Auto-focus input when opening
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const navItems: CommandItem[] = [
    { id: "nav-portfolio", label: "Portfolio", icon: LayoutDashboard, action: () => navigate("/"), category: "nav" },
    { id: "nav-screener", label: "Screener", icon: Search, action: () => navigate("/screener"), category: "nav" },
    { id: "nav-watchlist", label: "Watchlist", icon: Star, action: () => navigate("/watchlist"), category: "nav" },
    { id: "nav-recs", label: "Recommendations", icon: Lightbulb, action: () => navigate("/recommendations"), category: "nav" },
    { id: "nav-analyze", label: "Analyze", icon: Plus, action: () => navigate("/analyze"), category: "nav" },
    { id: "nav-log", label: "Decision Log", icon: BookOpen, action: () => navigate("/log"), category: "nav" },
    { id: "nav-learning", label: "Learning", icon: TrendingUp, action: () => navigate("/learning"), category: "nav" },
    { id: "nav-agents", label: "Agents", icon: Bot, action: () => navigate("/agents"), category: "nav" },
    { id: "nav-backtest", label: "Backtest", icon: Activity, action: () => navigate("/backtest"), category: "nav" },
    { id: "nav-health", label: "System Health", icon: Heart, action: () => navigate("/health"), category: "nav" },
    { id: "nav-settings", label: "Settings", icon: Settings, action: () => navigate("/settings"), category: "nav" },
  ];

  const recentItems: CommandItem[] = recentAnalyses.slice(0, 5).map((a) => ({
    id: `recent-${a.ticker}`,
    label: `${a.ticker} — ${a.decisionType}`,
    icon: TrendingUp,
    action: () => setOverlayTicker(a.ticker),
    category: "recent" as const,
  }));

  const allItems = [...navItems, ...recentItems];
  const filtered = query.trim()
    ? allItems.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()))
    : allItems;

  // Reset selection when query changes
  useEffect(() => {
    setSelectedIdx(0);
  }, [query]);

  const executeItem = (item: CommandItem) => {
    item.action();
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIdx]) {
      executeItem(filtered[selectedIdx]);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 60,
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "center",
            paddingTop: "15vh",
          }}
        >
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setOpen(false)}
            style={{
              position: "absolute",
              inset: 0,
              background: "rgba(0,0,0,0.5)",
              backdropFilter: "blur(4px)",
              WebkitBackdropFilter: "blur(4px)",
            }}
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
            style={{
              position: "relative",
              width: "100%",
              maxWidth: 480,
              margin: "0 var(--space-lg)",
              background: "var(--color-surface-1)",
              borderRadius: "var(--radius-lg)",
              border: "1px solid var(--glass-border)",
              boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
              overflow: "hidden",
            }}
          >
            {/* Search input */}
            <div style={{ padding: "var(--space-md) var(--space-lg)", borderBottom: "1px solid var(--glass-border)" }}>
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search pages, stocks..."
                style={{
                  width: "100%",
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  color: "var(--color-text-primary)",
                  fontSize: "var(--text-base)",
                  fontFamily: "inherit",
                }}
              />
            </div>

            {/* Results */}
            <div style={{ maxHeight: 320, overflowY: "auto", padding: "var(--space-sm) 0" }}>
              {filtered.length === 0 && (
                <div style={{ padding: "var(--space-lg)", textAlign: "center", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
                  No results
                </div>
              )}
              {filtered.map((item, i) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.id}
                    onClick={() => executeItem(item)}
                    onMouseEnter={() => setSelectedIdx(i)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-md)",
                      padding: "var(--space-sm) var(--space-lg)",
                      cursor: "pointer",
                      background: i === selectedIdx ? "var(--color-surface-2)" : "transparent",
                      transition: "background 0.1s ease",
                    }}
                  >
                    <Icon size={16} style={{ color: "var(--color-text-muted)", flexShrink: 0 }} />
                    <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-primary)" }}>
                      {item.label}
                    </span>
                    <span style={{ marginLeft: "auto", fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "capitalize" }}>
                      {item.category}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Footer */}
            <div style={{
              padding: "var(--space-sm) var(--space-lg)",
              borderTop: "1px solid var(--glass-border)",
              display: "flex",
              gap: "var(--space-lg)",
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
            }}>
              <span><kbd style={{ background: "var(--color-surface-2)", padding: "1px 4px", borderRadius: 3, fontSize: 10 }}>↑↓</kbd> navigate</span>
              <span><kbd style={{ background: "var(--color-surface-2)", padding: "1px 4px", borderRadius: 3, fontSize: 10 }}>↵</kbd> select</span>
              <span><kbd style={{ background: "var(--color-surface-2)", padding: "1px 4px", borderRadius: 3, fontSize: 10 }}>esc</kbd> close</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
