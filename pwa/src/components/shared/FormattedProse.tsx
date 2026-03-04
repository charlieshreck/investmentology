import { AnnotatedText } from "./AnnotatedText";

/**
 * Splits flat API prose into scannable bullet-point layout.
 * First sentence is bold lead; remaining sentences become compact bullets.
 * Financial terms are auto-annotated with glossary tooltips.
 */
export function FormattedProse({
  text,
  color = "var(--color-text-secondary)",
  fontSize = "var(--text-sm)",
}: {
  text: string;
  color?: string;
  fontSize?: string;
}) {
  if (!text) return null;

  // Split on sentence boundaries: period + space + uppercase, or period + newline
  const sentences = text
    .split(/(?<=\.)\s+(?=[A-Z])/)
    .map((s) => s.trim())
    .filter(Boolean);

  if (sentences.length <= 2) {
    // Short text: bold first sentence, plain second
    return (
      <div style={{ fontSize, color, lineHeight: 1.6 }}>
        <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>
          <AnnotatedText text={sentences[0]} />
        </span>
        {sentences[1] && <> <AnnotatedText text={sentences[1]} /></>}
      </div>
    );
  }

  // 3+ sentences: lead + bullet list
  const [lead, ...rest] = sentences;

  return (
    <div style={{ fontSize, color, lineHeight: 1.6 }}>
      <div style={{ fontWeight: 600, color: "var(--color-text-primary)", marginBottom: "var(--space-xs)" }}>
        <AnnotatedText text={lead} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {rest.map((s, i) => (
          <div key={i} style={{ display: "flex", gap: 6, alignItems: "baseline" }}>
            <span style={{ color: "var(--color-text-muted)", flexShrink: 0, fontSize: "0.7em" }}>·</span>
            <span><AnnotatedText text={s} /></span>
          </div>
        ))}
      </div>
    </div>
  );
}
