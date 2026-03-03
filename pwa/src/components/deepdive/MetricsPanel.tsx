import { CollapsiblePanel } from "./CollapsiblePanel";
import { Metric } from "./Metric";
import { FiftyTwoWeekBar } from "./FiftyTwoWeekBar";
import { Badge } from "../shared/Badge";
import { formatCap, formatNum, formatVol } from "../../utils/deepdiveHelpers";
import type { Profile, QuantGate, Fundamentals } from "../../views/StockDeepDive";

function zoneBadge(zone: string | null) {
  if (zone === "safe") return <Badge variant="success">Safe</Badge>;
  if (zone === "grey") return <Badge variant="warning">Grey</Badge>;
  if (zone === "distress") return <Badge variant="error">Distress</Badge>;
  return <Badge variant="neutral">N/A</Badge>;
}

function recBadge(rec: string) {
  const map: Record<string, "success" | "warning" | "error" | "neutral"> = {
    strong_buy: "success", buy: "success", hold: "warning",
    sell: "error", strong_sell: "error", underperform: "error",
  };
  return <Badge variant={map[rec] ?? "neutral"}>{rec.replace(/_/g, " ").toUpperCase()}</Badge>;
}

export function MetricsPanel({ profile, quantGate, fundamentals }: {
  profile: Profile | null;
  quantGate: QuantGate | null;
  fundamentals: Fundamentals | null;
}) {
  const p = profile;
  const q = quantGate;
  const f = fundamentals;

  // Build preview text
  const previewParts: string[] = [];
  if (p?.trailingPE != null) previewParts.push(`P/E ${p.trailingPE.toFixed(1)}`);
  if (f?.earnings_yield != null) previewParts.push(`EY ${(f.earnings_yield * 100).toFixed(1)}%`);
  if (q?.compositeScore != null) previewParts.push(`Composite ${q.compositeScore.toFixed(2)}`);
  if (q?.piotroskiScore != null) previewParts.push(`Piotroski ${q.piotroskiScore}/9`);
  const preview = previewParts.join(" | ") || "Metrics available";

  return (
    <CollapsiblePanel title="Metrics & Valuation" preview={preview}>
      {/* Valuation Ratios */}
      {p && (
        <div style={{ marginBottom: "var(--space-md)" }}>
          <div style={{
            fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-sm)",
          }}>
            Valuation
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "var(--space-md)" }}>
            {p.trailingPE != null && <Metric label="P/E (TTM)" value={p.trailingPE.toFixed(1)} mono />}
            {p.forwardPE != null && <Metric label="P/E (Fwd)" value={p.forwardPE.toFixed(1)} mono />}
            {p.priceToBook != null && <Metric label="P/B" value={p.priceToBook.toFixed(2)} mono />}
            {p.priceToSales != null && <Metric label="P/S" value={p.priceToSales.toFixed(2)} mono />}
            {f?.earnings_yield != null && <Metric label="Earnings Yield" value={`${(f.earnings_yield * 100).toFixed(1)}%`} mono />}
            {f?.roic != null && <Metric label="ROIC" value={`${(f.roic * 100).toFixed(0)}%`} mono />}
            {p.beta != null && <Metric label="Beta" value={p.beta.toFixed(2)} mono />}
            {p.dividendYield != null && <Metric label="Div Yield" value={`${p.dividendYield.toFixed(2)}%`} mono />}
            {p.averageVolume != null && <Metric label="Avg Volume" value={formatVol(p.averageVolume)} mono />}
          </div>
          {p.fiftyTwoWeekLow != null && p.fiftyTwoWeekHigh != null && f && (
            <div style={{ marginTop: "var(--space-md)" }}>
              <FiftyTwoWeekBar low={p.fiftyTwoWeekLow} high={p.fiftyTwoWeekHigh} current={f.price} />
            </div>
          )}
          {p.analystRecommendation && (
            <div style={{
              marginTop: "var(--space-md)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-md)",
              padding: "var(--space-md)",
              background: "var(--color-surface-0)",
              borderRadius: "var(--radius-sm)",
            }}>
              <div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Analyst Consensus</div>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
                  {recBadge(p.analystRecommendation)}
                  {p.analystCount != null && <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>({p.analystCount} analysts)</span>}
                </div>
              </div>
              {p.analystTarget != null && f && (
                <div style={{ marginLeft: "auto", textAlign: "right" }}>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>Target</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>${p.analystTarget.toFixed(0)}</div>
                  <div style={{
                    fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)",
                    color: p.analystTarget > f.price ? "var(--color-success)" : "var(--color-error)",
                  }}>
                    {p.analystTarget > f.price ? "+" : ""}{(((p.analystTarget - f.price) / f.price) * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Quant Gate Scores */}
      {q && (
        <div style={{
          marginBottom: "var(--space-md)",
          borderTop: p ? "1px solid var(--glass-border)" : undefined,
          paddingTop: p ? "var(--space-md)" : undefined,
        }}>
          <div style={{
            fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-sm)",
          }}>
            Quant Gate
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)", marginBottom: "var(--space-md)" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Composite</div>
              <div style={{
                fontSize: "var(--text-2xl)", fontWeight: 700, fontFamily: "var(--font-mono)",
                color: (q.compositeScore ?? 0) >= 0.7 ? "var(--color-success)" : (q.compositeScore ?? 0) >= 0.4 ? "var(--color-warning)" : "var(--color-error)",
              }}>
                {q.compositeScore?.toFixed(2) ?? "—"}
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Piotroski F</div>
              <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                {q.piotroskiScore}<span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>/9</span>
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginBottom: "var(--space-xs)" }}>Altman Z</div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-xs)" }}>
                <span style={{ fontSize: "var(--text-lg)", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{q.altmanZScore?.toFixed(1) ?? "—"}</span>
                {zoneBadge(q.altmanZone)}
              </div>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)" }}>
            <Metric label="Greenblatt Rank" value={`#${q.combinedRank}`} mono />
            <Metric label="EY Rank" value={`#${q.eyRank}`} mono />
            <Metric label="ROIC Rank" value={`#${q.roicRank}`} mono />
          </div>
        </div>
      )}

      {/* Fundamentals */}
      {f && (
        <div style={{
          borderTop: (p || q) ? "1px solid var(--glass-border)" : undefined,
          paddingTop: (p || q) ? "var(--space-md)" : undefined,
        }}>
          <div style={{
            fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 600,
            textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-sm)",
          }}>
            Fundamentals
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-md)" }}>
            <Metric label="Market Cap" value={formatCap(f.market_cap)} mono />
            <Metric label="EV" value={formatCap(f.enterprise_value)} mono />
            <Metric label="Revenue" value={formatNum(f.revenue)} mono />
            <Metric label="Net Income" value={formatNum(f.net_income)} mono />
            <Metric label="Op Income" value={formatNum(f.operating_income)} mono />
            <Metric label="Cash" value={formatNum(f.cash)} mono />
            <Metric label="Debt" value={formatNum(f.total_debt)} mono />
            <Metric label="Shares" value={`${(f.shares_outstanding / 1e6).toFixed(1)}M`} mono />
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-md)", textAlign: "right" }}>
            Data as of {new Date(f.fetched_at).toLocaleDateString()}
          </div>
        </div>
      )}
    </CollapsiblePanel>
  );
}
