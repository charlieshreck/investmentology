import { useState, useRef, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { findGlossaryTerms } from "../../utils/glossary";

/**
 * Renders text with inline glossary annotations.
 * Financial terms get a dotted underline — hover (desktop) or tap (mobile)
 * shows a tooltip with the plain-English definition.
 * Tooltip renders via portal so it escapes overflow:hidden containers.
 */
export function AnnotatedText({ text }: { text: string }) {
  const [activeTerm, setActiveTerm] = useState<string | null>(null);
  const [tooltipDef, setTooltipDef] = useState<string>("");
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const matches = findGlossaryTerms(text);
  if (!matches.length) return <>{text}</>;

  // Build segments: [plain, annotated, plain, annotated, ...]
  const segments: { text: string; definition?: string; key: string }[] = [];
  let cursor = 0;
  for (const m of matches) {
    if (m.index > cursor) {
      segments.push({ text: text.slice(cursor, m.index), key: `p${cursor}` });
    }
    segments.push({ text: text.slice(m.index, m.index + m.length), definition: m.definition, key: `t${m.index}` });
    cursor = m.index + m.length;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), key: `p${cursor}` });
  }

  return (
    <>
      {segments.map((seg) =>
        seg.definition ? (
          <GlossarySpan
            key={seg.key}
            text={seg.text}
            definition={seg.definition}
            isActive={activeTerm === seg.key}
            onActivate={(def, rect) => {
              clearTimeout(timeoutRef.current);
              setActiveTerm(seg.key);
              setTooltipDef(def);
              setTooltipPos({ x: rect.left + rect.width / 2, y: rect.top });
            }}
            onDeactivate={() => {
              timeoutRef.current = setTimeout(() => {
                setActiveTerm(null);
                setTooltipPos(null);
              }, 150);
            }}
          />
        ) : (
          <span key={seg.key}>{seg.text}</span>
        )
      )}
      {activeTerm && tooltipPos && createPortal(
        <GlossaryPopover
          definition={tooltipDef}
          x={tooltipPos.x}
          y={tooltipPos.y}
          onClose={() => { setActiveTerm(null); setTooltipPos(null); }}
          onMouseEnter={() => clearTimeout(timeoutRef.current)}
          onMouseLeave={() => { setActiveTerm(null); setTooltipPos(null); }}
        />,
        document.body,
      )}
    </>
  );
}

function GlossarySpan({ text, definition, isActive, onActivate, onDeactivate }: {
  text: string;
  definition: string;
  isActive: boolean;
  onActivate: (def: string, rect: DOMRect) => void;
  onDeactivate: () => void;
}) {
  const ref = useRef<HTMLSpanElement>(null!);

  const activate = useCallback(() => {
    if (ref.current) {
      onActivate(definition, ref.current.getBoundingClientRect());
    }
  }, [definition, onActivate]);

  return (
    <span
      ref={ref}
      onMouseEnter={activate}
      onMouseLeave={onDeactivate}
      onClick={(e) => { e.stopPropagation(); activate(); }}
      style={{
        textDecorationLine: "underline",
        textDecorationStyle: "dotted",
        textDecorationColor: isActive ? "var(--color-accent-bright)" : "var(--color-text-muted)",
        textUnderlineOffset: 2,
        cursor: "help",
        transition: "text-decoration-color 0.15s",
      }}
    >
      {text}
    </span>
  );
}

function GlossaryPopover({ definition, x, y, onClose, onMouseEnter, onMouseLeave }: {
  definition: string;
  x: number;
  y: number;
  onClose: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const popRef = useRef<HTMLDivElement>(null!);

  // Close on outside tap (mobile)
  useEffect(() => {
    const handler = (e: PointerEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [onClose]);

  return (
    <div
      ref={popRef}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{
        position: "fixed",
        left: x,
        top: y,
        transform: "translate(-50%, calc(-100% - 6px))",
        width: 240,
        padding: "8px 12px",
        background: "var(--color-surface-0)",
        border: "1px solid var(--glass-border)",
        borderRadius: "var(--radius-md)",
        boxShadow: "var(--shadow-elevated)",
        zIndex: 10000,
        pointerEvents: "auto",
      }}
    >
      <div style={{
        fontSize: 11,
        color: "var(--color-text-secondary)",
        lineHeight: 1.45,
      }}>
        {definition}
      </div>
    </div>
  );
}
