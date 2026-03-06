import { CollapsiblePanel } from "./CollapsiblePanel";
import { Badge } from "../shared/Badge";
import type { BuzzData, EarningsMomentum, NewsArticle } from "../../views/StockDeepDive";

interface EnrichmentPanelProps {
  news: NewsArticle[];
  buzz: BuzzData | null;
  earningsMomentum: EarningsMomentum | null;
}

function NewsItem({ article }: { article: NewsArticle }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "block",
        padding: "var(--space-sm) 0",
        borderBottom: "1px solid var(--color-surface-2)",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div
        style={{
          fontSize: "var(--text-sm)",
          fontWeight: 500,
          color: "var(--color-text-primary)",
          lineHeight: 1.3,
        }}
      >
        {article.title}
      </div>
      <div
        style={{
          display: "flex",
          gap: "var(--space-sm)",
          marginTop: 2,
          fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)",
        }}
      >
        <span>{article.publisher}</span>
        {article.published_at && (
          <>
            <span>&middot;</span>
            <span>{new Date(article.published_at).toLocaleDateString()}</span>
          </>
        )}
        {article.type && article.type !== "news" && (
          <Badge variant="neutral">{article.type}</Badge>
        )}
      </div>
    </a>
  );
}

export function EnrichmentPanel({ news, buzz, earningsMomentum }: EnrichmentPanelProps) {
  const hasContent = news.length > 0 || buzz || earningsMomentum;
  if (!hasContent) return null;

  const previewParts: string[] = [];
  if (news.length > 0) previewParts.push(`${news.length} articles`);
  if (buzz) previewParts.push(`Buzz: ${buzz.buzzLabel}`);
  if (earningsMomentum) previewParts.push(earningsMomentum.label.replace(/_/g, " "));

  return (
    <CollapsiblePanel
      title="Market Intel"
      preview={
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
          {previewParts.join(" · ")}
        </span>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-lg)" }}>
        {/* Buzz & Earnings Row */}
        {(buzz || earningsMomentum) && (
          <div
            style={{
              display: "flex",
              gap: "var(--space-lg)",
              flexWrap: "wrap",
            }}
          >
            {buzz && (
              <div style={{ flex: "1 1 140px" }}>
                <div
                  style={{
                    fontSize: "var(--text-xs)",
                    color: "var(--color-text-muted)",
                    marginBottom: 2,
                  }}
                >
                  Social Buzz
                </div>
                <div
                  style={{
                    fontSize: "var(--text-lg)",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                    color:
                      buzz.buzzScore > 2
                        ? "var(--color-warning)"
                        : "var(--color-text-secondary)",
                  }}
                >
                  {buzz.buzzLabel}
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {buzz.articleCount} articles · sentiment{" "}
                  {buzz.headlineSentiment != null
                    ? buzz.headlineSentiment > 0
                      ? "+"
                      : ""
                    : ""}
                  {buzz.headlineSentiment?.toFixed(2) ?? "n/a"}
                </div>
                {buzz.contrarianFlag && (
                  <Badge variant="warning">Contrarian signal</Badge>
                )}
              </div>
            )}

            {earningsMomentum && (
              <div style={{ flex: "1 1 140px" }}>
                <div
                  style={{
                    fontSize: "var(--text-xs)",
                    color: "var(--color-text-muted)",
                    marginBottom: 2,
                  }}
                >
                  Earnings Momentum
                </div>
                <div
                  style={{
                    fontSize: "var(--text-lg)",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                    color:
                      earningsMomentum.score > 0.5
                        ? "var(--color-success)"
                        : earningsMomentum.score < -0.5
                          ? "var(--color-error)"
                          : "var(--color-text-secondary)",
                  }}
                >
                  {earningsMomentum.label.replace(/_/g, " ")}
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                  {earningsMomentum.upwardRevisions} up · {earningsMomentum.downwardRevisions}{" "}
                  down · {earningsMomentum.beatStreak} beat streak
                </div>
              </div>
            )}
          </div>
        )}

        {/* News Articles */}
        {news.length > 0 && (
          <div>
            <div
              style={{
                fontSize: "var(--text-xs)",
                fontWeight: 600,
                color: "var(--color-text-secondary)",
                marginBottom: "var(--space-sm)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              Recent News
            </div>
            {news.slice(0, 8).map((article, i) => (
              <NewsItem key={i} article={article} />
            ))}
            {news.length > 8 && (
              <div
                style={{
                  fontSize: "var(--text-xs)",
                  color: "var(--color-text-muted)",
                  padding: "var(--space-sm) 0",
                  textAlign: "center",
                }}
              >
                + {news.length - 8} more articles
              </div>
            )}
          </div>
        )}
      </div>
    </CollapsiblePanel>
  );
}
