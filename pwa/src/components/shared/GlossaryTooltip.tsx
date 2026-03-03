import { useState } from "react";
import { lookupTerm } from "../../utils/glossary";
import { Info } from "lucide-react";

/**
 * Inline info icon that shows a glossary definition on click.
 * Use next to any financial term: <GlossaryTooltip term="altman z-score" />
 */
export function GlossaryTooltip({ term }: { term: string }) {
  const [open, setOpen] = useState(false);
  const definition = lookupTerm(term);
  if (!definition) return null;

  return (
    <span style={{ position: "relative", display: "inline-flex", alignItems: "center" }}>
      <button
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        style={{
          background: "none", border: "none", cursor: "pointer",
          padding: "0 2px", display: "inline-flex", alignItems: "center",
          color: "var(--color-text-muted)", opacity: 0.6,
        }}
      >
        <Info size={11} />
      </button>
      {open && (
        <>
          {/* Backdrop to close */}
          <div
            onClick={(e) => { e.stopPropagation(); setOpen(false); }}
            style={{ position: "fixed", inset: 0, zIndex: 99 }}
          />
          <div style={{
            position: "absolute",
            bottom: "calc(100% + 6px)",
            left: "50%",
            transform: "translateX(-50%)",
            width: 220,
            padding: "var(--space-sm) var(--space-md)",
            background: "var(--color-surface-0)",
            border: "1px solid var(--glass-border)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-elevated)",
            zIndex: 100,
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: "var(--color-accent-bright)",
              textTransform: "capitalize", marginBottom: 3,
            }}>
              {term}
            </div>
            <div style={{
              fontSize: 11, color: "var(--color-text-secondary)",
              lineHeight: 1.4,
            }}>
              {definition}
            </div>
          </div>
        </>
      )}
    </span>
  );
}
