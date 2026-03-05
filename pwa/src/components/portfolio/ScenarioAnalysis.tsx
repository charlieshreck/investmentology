import { useState } from "react";
import { motion } from "framer-motion";
import { formatCurrency } from "../../utils/format";

interface SectorSlice {
  name: string;
  pct: number;
  value: number;
  color: string;
}

interface ScenarioResult {
  ticker: string;
  action: string;
  shares: number;
  price: number;
  before: {
    totalValue: number;
    cashReserve: number;
    positionCount: number;
    sectors: SectorSlice[];
  };
  after: {
    totalValue: number;
    cashReserve: number;
    positionCount: number;
    sectors: SectorSlice[];
  };
  warnings: string[];
  canProceed: boolean;
  error?: string;
}

export function ScenarioAnalysis({
  ticker,
  currentPrice,
  onClose,
  onProceed,
}: {
  ticker: string;
  currentPrice?: number;
  onClose: () => void;
  onProceed?: (ticker: string, shares: number, price: number) => void;
}) {
  const [action, setAction] = useState<"add" | "remove" | "resize">("add");
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState(currentPrice?.toString() ?? "");
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runScenario = async () => {
    const s = parseFloat(shares);
    const p = parseFloat(price) || undefined;
    if (!s || s <= 0) {
      setError("Enter a valid number of shares");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/invest/portfolio/scenario", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ticker, shares: s, price: p }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        setResult(null);
      } else {
        setResult(data);
      }
    } catch {
      setError("Failed to evaluate scenario");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.7)",
        backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "var(--space-lg)",
      }}
    >
      <motion.div
        initial={{ scale: 0.95, y: 10 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.95, y: 10 }}
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-surface-1)",
          borderRadius: "var(--radius-xl)",
          padding: "var(--space-xl)",
          width: "100%",
          maxWidth: 500,
          maxHeight: "90vh",
          overflowY: "auto",
          border: "1px solid var(--glass-border)",
          boxShadow: "var(--shadow-elevated)",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-lg)" }}>
          <div style={{ fontSize: "var(--text-lg)", fontWeight: 700 }}>
            Scenario: {ticker}
          </div>
          <button onClick={onClose} style={{
            background: "none", border: "none", color: "var(--color-text-muted)",
            fontSize: 18, cursor: "pointer", padding: 4,
          }}>
            &times;
          </button>
        </div>

        {/* Input form */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          {/* Action selector */}
          <div style={{ display: "flex", gap: "var(--space-xs)" }}>
            {(["add", "remove", "resize"] as const).map((a) => (
              <button
                key={a}
                onClick={() => setAction(a)}
                style={{
                  flex: 1,
                  padding: "6px 0",
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: "capitalize",
                  border: "1px solid",
                  borderColor: action === a ? "var(--color-accent)" : "var(--color-surface-2)",
                  borderRadius: "var(--radius-sm)",
                  background: action === a ? "var(--color-accent-ghost)" : "transparent",
                  color: action === a ? "var(--color-accent-bright)" : "var(--color-text-muted)",
                  cursor: "pointer",
                }}
              >
                {a}
              </button>
            ))}
          </div>

          {/* Shares + Price */}
          <div style={{ display: "flex", gap: "var(--space-sm)" }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>
                Shares
              </label>
              <input
                type="number"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                placeholder="10"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  fontSize: 14,
                  background: "var(--color-surface-0)",
                  border: "1px solid var(--color-surface-2)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--color-text)",
                  outline: "none",
                }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 11, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>
                Price (optional)
              </label>
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="Auto"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  fontSize: 14,
                  background: "var(--color-surface-0)",
                  border: "1px solid var(--color-surface-2)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--color-text)",
                  outline: "none",
                }}
              />
            </div>
          </div>

          <button
            onClick={runScenario}
            disabled={loading}
            style={{
              padding: "10px 0",
              fontSize: 13,
              fontWeight: 700,
              background: "var(--color-accent)",
              color: "#fff",
              border: "none",
              borderRadius: "var(--radius-md)",
              cursor: loading ? "wait" : "pointer",
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? "Evaluating..." : "Run Scenario"}
          </button>

          {error && (
            <div style={{ fontSize: 12, color: "var(--color-danger)", padding: "8px 12px", background: "rgba(239,68,68,0.08)", borderRadius: "var(--radius-sm)" }}>
              {error}
            </div>
          )}
        </div>

        {/* Results */}
        {result && (
          <div style={{ marginTop: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            {/* Before / After comparison */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-sm)" }}>
              <ComparisonCard label="Before" data={result.before} />
              <ComparisonCard label="After" data={result.after} />
            </div>

            {/* Sector comparison */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-sm)" }}>
              <SectorBar sectors={result.before.sectors} label="Before" />
              <SectorBar sectors={result.after.sectors} label="After" />
            </div>

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div style={{
                padding: "10px 14px",
                background: "rgba(251, 191, 36, 0.08)",
                border: "1px solid rgba(251, 191, 36, 0.2)",
                borderRadius: "var(--radius-md)",
                fontSize: 12,
              }}>
                <div style={{ fontWeight: 700, color: "var(--color-warning)", marginBottom: 4 }}>
                  Warnings
                </div>
                {result.warnings.map((w, i) => (
                  <div key={i} style={{ color: "var(--color-text-secondary)", marginTop: 2 }}>
                    {w}
                  </div>
                ))}
              </div>
            )}

            {/* Proceed button */}
            {result.canProceed && onProceed && action === "add" && (
              <button
                onClick={() => onProceed(ticker, parseFloat(shares), result.price)}
                style={{
                  padding: "10px 0",
                  fontSize: 13,
                  fontWeight: 700,
                  background: "var(--color-success)",
                  color: "#fff",
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  cursor: "pointer",
                }}
              >
                Proceed to Buy
              </button>
            )}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

function ComparisonCard({ label, data }: {
  label: string;
  data: { totalValue: number; cashReserve: number; positionCount: number };
}) {
  return (
    <div style={{
      padding: "12px",
      background: "var(--color-surface-0)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--color-surface-2)",
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)" }}>
        {formatCurrency(data.totalValue)}
      </div>
      <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>
        Cash: {formatCurrency(data.cashReserve)}
      </div>
      <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
        {data.positionCount} position{data.positionCount !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

function SectorBar({ sectors, label }: { sectors: SectorSlice[]; label: string }) {
  return (
    <div style={{
      padding: "12px",
      background: "var(--color-surface-0)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--color-surface-2)",
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
        {label} Sectors
      </div>
      {/* Stacked bar */}
      <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", marginBottom: 8 }}>
        {sectors.map((s, i) => (
          <div
            key={i}
            style={{
              width: `${s.pct}%`,
              background: s.color,
              minWidth: s.pct > 0 ? 2 : 0,
            }}
            title={`${s.name}: ${s.pct}%`}
          />
        ))}
      </div>
      {/* Legend */}
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {sectors.slice(0, 4).map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.color, flexShrink: 0 }} />
            <span style={{ color: "var(--color-text-muted)" }}>{s.name}</span>
            <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)" }}>{s.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
