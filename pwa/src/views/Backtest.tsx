import { useState, useEffect, useRef } from "react";
import { ViewHeader } from "../components/layout/ViewHeader";
import { BentoCard } from "../components/shared/BentoCard";
import { Badge } from "../components/shared/Badge";
import { useBacktest } from "../hooks/useBacktest";

function formatCurrency(n: number): string {
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

function formatPct(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function pnlColor(n: number): string {
  return n > 0 ? "var(--color-success)" : n < 0 ? "var(--color-error)" : "var(--color-text-secondary)";
}

function EquityCurve({ data }: { data: { date: string; value: number }[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length < 2) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = 600;
    const H = 200;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const values = data.map((d) => d.value);
    const min = Math.min(...values) * 0.995;
    const max = Math.max(...values) * 1.005;
    const range = max - min || 1;

    // Draw grid
    ctx.strokeStyle = "rgba(255,255,255,0.05)";
    ctx.lineWidth = 1;
    for (let i = 0; i < 4; i++) {
      const y = (H / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }

    // Draw equity curve
    const startValue = values[0];
    ctx.beginPath();
    ctx.strokeStyle = "#818cf8";
    ctx.lineWidth = 2;

    for (let i = 0; i < values.length; i++) {
      const x = (i / (values.length - 1)) * W;
      const y = H - ((values[i] - min) / range) * H;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Fill area with gradient
    ctx.lineTo(W, H);
    ctx.lineTo(0, H);
    ctx.closePath();

    const gradient = ctx.createLinearGradient(0, 0, 0, H);
    const isProfit = values[values.length - 1] >= startValue;
    gradient.addColorStop(0, isProfit ? "rgba(52, 211, 153, 0.3)" : "rgba(248, 113, 113, 0.3)");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradient;
    ctx.fill();
  }, [data]);

  return <canvas ref={canvasRef} style={{ width: "100%", height: 200 }} />;
}

export function Backtest() {
  const { result, history, loading, error, runBacktest, fetchHistory } = useBacktest();
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [capital, setCapital] = useState("100000");

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runBacktest(startDate, endDate, parseFloat(capital) || 100000);
  };

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <ViewHeader title="Backtest" subtitle="Strategy validation" />

      <div style={{ padding: "var(--space-lg)", display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Input form */}
        <BentoCard title="Run Backtest">
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)" }}>
              <label style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                Start Date
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  style={{
                    display: "block",
                    width: "100%",
                    marginTop: 4,
                    padding: "var(--space-sm) var(--space-md)",
                    background: "var(--color-surface-1)",
                    border: "1px solid var(--glass-border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--color-text)",
                    fontSize: "var(--text-sm)",
                  }}
                />
              </label>
              <label style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                End Date
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  style={{
                    display: "block",
                    width: "100%",
                    marginTop: 4,
                    padding: "var(--space-sm) var(--space-md)",
                    background: "var(--color-surface-1)",
                    border: "1px solid var(--glass-border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--color-text)",
                    fontSize: "var(--text-sm)",
                  }}
                />
              </label>
              <label style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                Capital ($)
                <input
                  type="number"
                  value={capital}
                  onChange={(e) => setCapital(e.target.value)}
                  style={{
                    display: "block",
                    width: "100%",
                    marginTop: 4,
                    padding: "var(--space-sm) var(--space-md)",
                    background: "var(--color-surface-1)",
                    border: "1px solid var(--glass-border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--color-text)",
                    fontSize: "var(--text-sm)",
                    fontFamily: "var(--font-mono)",
                  }}
                />
              </label>
            </div>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: "var(--space-md) var(--space-xl)",
                background: loading ? "var(--color-surface-2)" : "var(--gradient-active)",
                border: "none",
                borderRadius: "var(--radius-sm)",
                color: loading ? "var(--color-text-muted)" : "white",
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
                alignSelf: "flex-start",
              }}
            >
              {loading ? "Running backtest..." : "Run Backtest"}
            </button>
          </form>
        </BentoCard>

        {error && (
          <BentoCard>
            <Badge variant="error">Error</Badge>
            <p style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-sm)", marginTop: "var(--space-sm)" }}>
              {error}
            </p>
          </BentoCard>
        )}

        {/* Results */}
        {result && (
          <>
            {/* Key stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--space-md)" }}>
              <BentoCard title="Total Return">
                <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: pnlColor(result.summary.totalReturn) }}>
                  {formatPct(result.summary.totalReturn)}
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  Annualized: {formatPct(result.summary.annualizedReturn)}
                </div>
              </BentoCard>
              <BentoCard title="Sharpe Ratio">
                <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: result.summary.sharpeRatio >= 1 ? "var(--color-success)" : "var(--color-warning)" }}>
                  {result.summary.sharpeRatio.toFixed(2)}
                </div>
              </BentoCard>
              <BentoCard title="Max Drawdown">
                <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--color-error)" }}>
                  -{result.summary.maxDrawdown.toFixed(1)}%
                </div>
              </BentoCard>
              <BentoCard title="Win Rate">
                <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  {result.summary.winRate.toFixed(0)}%
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {result.summary.winningTrades}W / {result.summary.losingTrades}L
                </div>
              </BentoCard>
            </div>

            {/* Equity curve */}
            <BentoCard title="Equity Curve">
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-sm)" }}>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {formatCurrency(result.summary.initialCapital)} start
                </span>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                  {formatCurrency(result.summary.finalValue)} end
                </span>
              </div>
              <EquityCurve data={result.equityCurve} />
            </BentoCard>

            {/* Monthly returns */}
            {result.monthlyReturns.length > 0 && (
              <BentoCard title="Monthly Returns">
                <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-xs)" }}>
                  {result.monthlyReturns.map((m) => (
                    <div
                      key={m.month}
                      style={{
                        padding: "var(--space-xs) var(--space-sm)",
                        borderRadius: "var(--radius-sm)",
                        background: m.return > 0
                          ? `rgba(52, 211, 153, ${Math.min(Math.abs(m.return) / 10, 0.6)})`
                          : m.return < 0
                          ? `rgba(248, 113, 113, ${Math.min(Math.abs(m.return) / 10, 0.6)})`
                          : "var(--color-surface-1)",
                        fontSize: "var(--text-xs)",
                        fontFamily: "var(--font-mono)",
                        color: "var(--color-text)",
                      }}
                    >
                      {m.month}: {formatPct(m.return)}
                    </div>
                  ))}
                </div>
              </BentoCard>
            )}

            {/* Trades */}
            {result.trades.length > 0 && (
              <BentoCard title={`Trades (${result.trades.length})`}>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
                    <thead>
                      <tr>
                        {["Ticker", "Entry", "Exit", "P&L %", "Days"].map((h) => (
                          <th
                            key={h}
                            style={{
                              textAlign: h === "Ticker" ? "left" : "right",
                              padding: "var(--space-sm) var(--space-md)",
                              color: "var(--color-text-muted)",
                              fontWeight: 500,
                              fontSize: "var(--text-xs)",
                              borderBottom: "1px solid var(--glass-border)",
                            }}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.trades.map((t, i) => (
                        <tr key={i}>
                          <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", fontWeight: 600 }}>
                            {t.ticker}
                          </td>
                          <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                            ${t.entryPrice.toFixed(2)}
                          </td>
                          <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)" }}>
                            {t.exitPrice ? `$${t.exitPrice.toFixed(2)}` : "—"}
                          </td>
                          <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right", fontFamily: "var(--font-mono)", color: pnlColor(t.pnlPct) }}>
                            {formatPct(t.pnlPct)}
                          </td>
                          <td style={{ padding: "var(--space-sm) var(--space-md)", borderBottom: "1px solid var(--glass-border)", textAlign: "right" }}>
                            {t.holdingDays}d
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </BentoCard>
            )}
          </>
        )}

        {/* History */}
        {history.length > 0 && (
          <BentoCard title="Past Runs">
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
              {history.map((h) => (
                <div
                  key={h.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "var(--space-sm) var(--space-md)",
                    background: "var(--color-surface-0)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "var(--text-sm)",
                  }}
                >
                  <span style={{ color: "var(--color-text-secondary)" }}>
                    {h.startDate} — {h.endDate}
                  </span>
                  <div style={{ display: "flex", gap: "var(--space-md)", fontFamily: "var(--font-mono)" }}>
                    <span style={{ color: pnlColor(h.totalReturn) }}>{formatPct(h.totalReturn)}</span>
                    <span style={{ color: "var(--color-text-muted)" }}>SR {h.sharpeRatio.toFixed(2)}</span>
                    <span style={{ color: "var(--color-text-muted)" }}>{h.totalTrades} trades</span>
                  </div>
                </div>
              ))}
            </div>
          </BentoCard>
        )}

        <div style={{ height: "var(--nav-height)" }} />
      </div>
    </div>
  );
}
