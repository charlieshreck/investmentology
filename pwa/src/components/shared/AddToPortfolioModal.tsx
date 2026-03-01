import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface AddToPortfolioModalProps {
  ticker: string;
  currentPrice: number;
  defaultThesis?: string;
  onClose: () => void;
  onSuccess?: (msg: string) => void;
  onError?: (msg: string) => void;
}

function formatPrice(n: number): string {
  return n > 0 ? `$${n.toFixed(2)}` : "—";
}

export function AddToPortfolioModal({
  ticker,
  currentPrice,
  defaultThesis = "",
  onClose,
  onSuccess,
  onError,
}: AddToPortfolioModalProps) {
  const [entryPrice, setEntryPrice] = useState(currentPrice > 0 ? currentPrice.toString() : "");
  const [shares, setShares] = useState("100");

  // Fetch live price if currentPrice is missing/zero
  useEffect(() => {
    if (currentPrice > 0) return;
    let cancelled = false;
    fetch(`/api/invest/stock/${ticker}/chart?period=1w`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (cancelled || !d?.data?.length) return;
        const lastPrice = d.data[d.data.length - 1]?.close;
        if (lastPrice > 0) setEntryPrice(lastPrice.toFixed(2));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [ticker, currentPrice]);
  const [posType, setPosType] = useState("core");
  const [thesis, setThesis] = useState(defaultThesis.slice(0, 200));
  const [submitting, setSubmitting] = useState(false);

  const price = parseFloat(entryPrice) || 0;
  const qty = parseFloat(shares) || 0;
  const totalCost = price * qty;

  const handleSubmit = async () => {
    if (price <= 0 || qty <= 0) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/invest/portfolio/positions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker,
          entry_price: price,
          shares: qty,
          position_type: posType,
          thesis,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onSuccess?.(`Added ${ticker} (${qty} shares @ ${formatPrice(price)})`);
      onClose();
    } catch (err) {
      onError?.(`Error: ${err instanceof Error ? err.message : "failed"}`);
    } finally {
      setSubmitting(false);
    }
  };

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center",
        padding: "var(--space-lg)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-surface-1)", borderRadius: "var(--radius-lg)",
          padding: "var(--space-xl)", width: "100%", maxWidth: 400,
          display: "flex", flexDirection: "column", gap: "var(--space-md)",
        }}
      >
        <div style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>
          Add {ticker} to Portfolio
        </div>

        {/* Price + Shares side by side */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
          <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
            Price per share
            <input
              type="number"
              step="0.01"
              value={entryPrice}
              onChange={(e) => setEntryPrice(e.target.value)}
              style={{
                width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
                background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
                borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
                fontFamily: "var(--font-mono)",
              }}
            />
          </label>
          <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
            Shares
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              style={{
                width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
                background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
                borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
                fontFamily: "var(--font-mono)",
              }}
            />
          </label>
        </div>

        {/* Cost summary */}
        {price > 0 && qty > 0 && (
          <div style={{
            padding: "var(--space-md)",
            background: "var(--color-surface-0)",
            borderRadius: "var(--radius-sm)",
            display: "flex", flexDirection: "column", gap: "var(--space-xs)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
              <span>{qty} shares @ {formatPrice(price)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>Total cost</span>
              <span style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                {totalCost.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 })}
              </span>
            </div>
          </div>
        )}

        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
          Position Type
          <select
            value={posType}
            onChange={(e) => setPosType(e.target.value)}
            style={{
              width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
            }}
          >
            <option value="core">Core</option>
            <option value="tactical">Tactical</option>
            <option value="permanent">Permanent</option>
          </select>
        </label>

        <label style={{ fontSize: "var(--text-sm)", fontWeight: 500 }}>
          Thesis
          <textarea
            value={thesis}
            onChange={(e) => setThesis(e.target.value)}
            rows={2}
            style={{
              width: "100%", marginTop: 4, padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)", color: "var(--color-text-primary)",
              fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", resize: "vertical",
            }}
          />
        </label>

        <div style={{ display: "flex", gap: "var(--space-md)", marginTop: "var(--space-sm)" }}>
          <button
            onClick={onClose}
            disabled={submitting}
            style={{
              flex: 1, padding: "var(--space-sm) var(--space-md)",
              background: "var(--color-surface-0)", border: "1px solid var(--glass-border)",
              borderRadius: "var(--radius-sm)", color: "var(--color-text-secondary)", cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={price <= 0 || qty <= 0 || submitting}
            style={{
              flex: 1, padding: "var(--space-sm) var(--space-md)",
              background: price > 0 && qty > 0 && !submitting ? "var(--gradient-active)" : "var(--color-surface-2)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: price > 0 && qty > 0 && !submitting ? "#fff" : "var(--color-text-muted)",
              cursor: price > 0 && qty > 0 && !submitting ? "pointer" : "default",
              fontWeight: 600,
            }}
          >
            {submitting ? "Adding..." : "Add Position"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
