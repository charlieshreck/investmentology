import { useState } from "react";
import { BentoCard } from "../shared/BentoCard";
import { Badge } from "../shared/Badge";
import { verdictColor, verdictLabel, verdictBadgeVariant } from "../../utils/verdictHelpers";
import type {
  VerdictData,
  Signal,
  Decision,
  NewsArticle,
  WatchlistInfo,
} from "../../views/StockDeepDive";

function signalVerdictVariant(v: string): "success" | "error" | "warning" | "neutral" {
  const upper = String(v).toUpperCase();
  if (upper === "BUY" || upper === "STRONG_BUY") return "success";
  if (upper === "SELL" || upper === "AVOID") return "error";
  if (upper === "HOLD" || upper === "ACCUMULATE") return "warning";
  return "neutral";
}

function SignalRow({ signal }: { signal: Signal }) {
  const [expanded, setExpanded] = useState(false);
  const sigs = signal.signals ?? {};
  const verdict = sigs.verdict as string | undefined;
  const targetPrice = sigs.target_price as number | undefined;
  const riskFlags = (sigs.risk_flags ?? sigs.risks) as string[] | undefined;
  const confidenceFactors = (sigs.confidence_factors ?? sigs.catalysts) as string[] | undefined;

  return (
    <div style={{ background: "var(--color-surface-0)", borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex", alignItems: "center", gap: "var(--space-md)",
          padding: "var(--space-sm) var(--space-md)", cursor: "pointer",
        }}
      >
        <span style={{ fontWeight: 600, fontSize: "var(--text-sm)", minWidth: 64 }}>
          {signal.agentName.charAt(0).toUpperCase() + signal.agentName.slice(1)}
        </span>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", minWidth: 60 }}>{signal.model}</span>
        {verdict && (
          <Badge variant={signalVerdictVariant(verdict)}>{verdict}</Badge>
        )}
        {targetPrice != null && targetPrice > 0 && (
          <span style={{ fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)", color: "var(--color-accent-bright)" }}>
            ${targetPrice.toFixed(0)}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {signal.confidence != null && (
          <Badge variant={signal.confidence >= 0.7 ? "success" : signal.confidence >= 0.4 ? "warning" : "error"}>
            {(signal.confidence * 100).toFixed(0)}%
          </Badge>
        )}
        <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>
          ▼
        </span>
      </div>
      {expanded && (
        <div style={{ padding: "0 var(--space-md) var(--space-md)", borderTop: "1px solid var(--glass-border)" }}>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
            {signal.reasoning}
          </div>
          {/* Signal tags */}
          {(confidenceFactors?.length || riskFlags?.length) && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-xs)", marginTop: "var(--space-sm)" }}>
              {confidenceFactors?.map((f, i) => (
                <span key={`cf-${i}`} style={{
                  padding: "1px var(--space-sm)", fontSize: 10, fontFamily: "var(--font-mono)",
                  background: "rgba(74, 222, 128, 0.1)", border: "1px solid rgba(74, 222, 128, 0.3)",
                  borderRadius: "var(--radius-sm)", color: "var(--color-success)",
                }}>
                  {f}
                </span>
              ))}
              {riskFlags?.map((f, i) => (
                <span key={`rf-${i}`} style={{
                  padding: "1px var(--space-sm)", fontSize: 10, fontFamily: "var(--font-mono)",
                  background: "rgba(248, 113, 113, 0.1)", border: "1px solid rgba(248, 113, 113, 0.3)",
                  borderRadius: "var(--radius-sm)", color: "var(--color-error)",
                }}>
                  {f}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function stateBadge(state: string) {
  const map: Record<string, "accent" | "success" | "warning" | "error" | "neutral"> = {
    CANDIDATE: "accent", CONVICTION_BUY: "success", POSITION_HOLD: "success",
    WATCHLIST_EARLY: "accent", WATCHLIST_CATALYST: "warning",
    REJECTED: "error", POSITION_SELL: "warning",
  };
  return <Badge variant={map[state] ?? "neutral"}>{state.replace(/_/g, " ")}</Badge>;
}

interface ArchiveSectionProps {
  verdictHistory: VerdictData[];
  signals: Signal[];
  decisions: Decision[];
  news: NewsArticle[];
  businessSummary: string | null;
  watchlist: WatchlistInfo | null;
}

export function ArchiveSection({
  verdictHistory,
  signals,
  decisions,
  news,
  businessSummary,
  watchlist,
}: ArchiveSectionProps) {
  const hasContent =
    verdictHistory.length > 1 ||
    signals.length > 0 ||
    decisions.length > 0 ||
    news.length > 0 ||
    !!businessSummary ||
    !!watchlist;

  if (!hasContent) return null;

  return (
    <>
      {/* Archive separator */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-md)",
        margin: "var(--space-md) 0",
      }}>
        <div style={{ flex: 1, borderTop: "1px dashed var(--glass-border)" }} />
        <span style={{
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
          fontWeight: 600,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
        }}>
          Full Archive
        </span>
        <div style={{ flex: 1, borderTop: "1px dashed var(--glass-border)" }} />
      </div>

      {/* Verdict History Timeline */}
      {verdictHistory.length > 1 && (
        <BentoCard title="Verdict History">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xs)" }}>
            {verdictHistory.map((v, i) => {
              const vColor = verdictColor[v.recommendation] ?? "var(--color-text-muted)";
              const vLbl = verdictLabel[v.recommendation] ?? v.recommendation;
              const vVariant = verdictBadgeVariant[v.recommendation] ?? "neutral";
              return (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: "var(--space-md)",
                  padding: "var(--space-sm) var(--space-md)",
                  borderLeft: i === 0 ? `3px solid ${vColor}` : "3px solid var(--glass-border)",
                  background: i === 0 ? "var(--color-surface-1)" : "transparent",
                  borderRadius: "0 var(--radius-sm) var(--radius-sm) 0",
                }}>
                  <Badge variant={vVariant}>{vLbl}</Badge>
                  {v.confidence != null && (
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                      {(v.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  {v.consensusScore != null && (
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                      cs:{v.consensusScore > 0 ? "+" : ""}{v.consensusScore.toFixed(2)}
                    </span>
                  )}
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginLeft: "auto" }}>
                    {v.createdAt ? new Date(v.createdAt).toLocaleDateString() : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </BentoCard>
      )}

      {/* Agent Signals */}
      {signals.length > 0 && (
        <BentoCard title="Agent Signals">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {signals.map((s, i) => (
              <SignalRow key={i} signal={s} />
            ))}
          </div>
        </BentoCard>
      )}

      {/* Decision History */}
      {decisions.length > 0 && (
        <BentoCard title="Decision History">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {decisions.map((d) => (
              <div key={d.id} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "var(--space-md)", borderBottom: "1px solid var(--glass-border)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", flexWrap: "wrap" }}>
                  <Badge variant="neutral">{d.decisionType}</Badge>
                  {d.outcome && (
                    <Badge variant={
                      d.outcome === "correct" ? "success"
                      : d.outcome === "incorrect" ? "error"
                      : "neutral"
                    }>
                      {d.outcome}
                    </Badge>
                  )}
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                    {d.layer} — {d.createdAt ? new Date(d.createdAt).toLocaleDateString() : ""}
                    {d.settledAt && ` (settled ${new Date(d.settledAt).toLocaleDateString()})`}
                  </span>
                </div>
                {d.confidence != null && (
                  <Badge variant={d.confidence >= 0.7 ? "success" : d.confidence >= 0.4 ? "warning" : "error"}>
                    {(d.confidence * 100).toFixed(0)}%
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </BentoCard>
      )}

      {/* News */}
      {news.length > 0 && (
        <BentoCard title="Recent News">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            {news.map((article, i) => (
              <a
                key={i}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "block", padding: "var(--space-md)", borderRadius: "var(--radius-sm)",
                  background: "var(--color-surface-0)", textDecoration: "none", color: "inherit",
                  transition: "background var(--duration-fast) var(--ease-out)",
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-1)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--color-surface-0)"; }}
              >
                <div style={{ fontWeight: 600, fontSize: "var(--text-sm)", marginBottom: "var(--space-xs)", color: "var(--color-text-primary)" }}>
                  {article.title}
                </div>
                {article.summary && (
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", lineHeight: 1.5, marginBottom: "var(--space-xs)" }}>
                    {article.summary.length > 160 ? article.summary.slice(0, 160) + "..." : article.summary}
                  </div>
                )}
                <div style={{ display: "flex", gap: "var(--space-md)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {article.publisher && <span>{article.publisher}</span>}
                  {article.published_at && <span>{new Date(article.published_at).toLocaleDateString()}</span>}
                </div>
              </a>
            ))}
          </div>
        </BentoCard>
      )}

      {/* Business Summary */}
      {businessSummary && (
        <BentoCard title="Business">
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.7 }}>
            {businessSummary}
          </div>
        </BentoCard>
      )}

      {/* Watchlist Info */}
      {watchlist && (
        <BentoCard title="Watchlist">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              {stateBadge(watchlist.state)}
              {watchlist.notes && (
                <span style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginLeft: "var(--space-md)" }}>
                  {watchlist.notes}
                </span>
              )}
            </div>
            {watchlist.updated_at && (
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                {new Date(watchlist.updated_at).toLocaleDateString()}
              </span>
            )}
          </div>
        </BentoCard>
      )}
    </>
  );
}
