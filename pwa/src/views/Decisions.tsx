import { useEffect, useState, useCallback, useRef } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { useDecisions } from "../hooks/useDecisions";

function decisionVariant(type: string): "accent" | "success" | "warning" | "error" | "neutral" {
  const map: Record<string, "accent" | "success" | "warning" | "error" | "neutral"> = {
    BUY: "success",
    SELL: "error",
    TRIM: "warning",
    HOLD: "accent",
    REJECT: "error",
    WATCHLIST: "neutral",
    SCREEN: "neutral",
    COMPETENCE_PASS: "success",
    COMPETENCE_FAIL: "error",
    AGENT_ANALYSIS: "accent",
    PATTERN_MATCH: "accent",
    ADVERSARIAL_REVIEW: "warning",
  };
  return map[type] ?? "neutral";
}

export function Decisions() {
  const { decisions, total, page, loading, error, fetchPage } = useDecisions();
  const [filterTicker, setFilterTicker] = useState("");
  const [filterType, setFilterType] = useState("");
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchPage(1);
  }, [fetchPage]);

  // Infinite scroll observer
  const loadMore = useCallback(() => {
    if (!loading && decisions.length < total) {
      fetchPage(page + 1);
    }
  }, [loading, decisions.length, total, page, fetchPage]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) loadMore(); },
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  const filtered = decisions.filter((d) => {
    if (filterTicker && !d.ticker.toLowerCase().includes(filterTicker.toLowerCase())) return false;
    if (filterType && d.decisionType !== filterType) return false;
    return true;
  });

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader
        title="Decision Log"
        subtitle={`${total} decisions`}
      />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Filters */}
        <div style={{ display: "flex", gap: "var(--space-md)" }}>
          <input
            type="text"
            placeholder="Filter ticker..."
            value={filterTicker}
            onChange={(e) => setFilterTicker(e.target.value)}
            style={{
              flex: 1,
              padding: "var(--space-md) var(--space-lg)",
              background: "var(--color-surface-1)",
              border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-text)",
              fontSize: "var(--text-sm)",
              fontFamily: "var(--font-sans)",
              outline: "none",
            }}
          />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{
              padding: "var(--space-md) var(--space-lg)",
              background: "var(--color-surface-1)",
              border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-text)",
              fontSize: "var(--text-sm)",
              fontFamily: "var(--font-sans)",
              outline: "none",
            }}
          >
            <option value="">All Types</option>
            {["SCREEN", "COMPETENCE_PASS", "COMPETENCE_FAIL", "AGENT_ANALYSIS", "PATTERN_MATCH", "ADVERSARIAL_REVIEW", "BUY", "SELL", "TRIM", "HOLD", "REJECT", "WATCHLIST"].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        {error && (
          <BentoCard>
            <p style={{ color: "var(--color-error)" }}>Error: {error}</p>
          </BentoCard>
        )}

        {/* Decision list */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
          {filtered.map((d) => (
            <div
              key={d.id}
              style={{
                padding: "var(--space-lg)",
                background: "var(--glass-bg)",
                backdropFilter: `blur(var(--glass-blur))`,
                border: "1px solid var(--glass-border)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-sm)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
                  <span style={{ fontWeight: 600, color: "var(--color-accent-bright)" }}>{d.ticker}</span>
                  <Badge variant={decisionVariant(d.decisionType)}>{d.decisionType}</Badge>
                </div>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                  {(d.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.4 }}>
                {d.reasoning}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "var(--space-md)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                <span>{d.layer}</span>
                <span>{new Date(d.createdAt).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>

        {loading && (
          <p style={{ textAlign: "center", color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Loading...</p>
        )}

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} style={{ height: 1 }} />

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}
