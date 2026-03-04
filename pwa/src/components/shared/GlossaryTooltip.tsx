import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { lookupTerm } from "../../utils/glossary";

/**
 * Inline ? icon that shows a glossary definition.
 * Hover on desktop, tap on mobile.
 * Renders tooltip via portal so it escapes overflow:hidden containers.
 */
export function GlossaryTooltip({ term }: { term: string }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const btnRef = useRef<HTMLButtonElement>(null!);
  const popRef = useRef<HTMLDivElement>(null!);
  const definition = lookupTerm(term);
  if (!definition) return null;

  const updatePos = () => {
    if (btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      setPos({ x: r.left + r.width / 2, y: r.top });
    }
  };

  const show = useCallback(() => {
    clearTimeout(timeoutRef.current);
    updatePos();
    setOpen(true);
  }, []);

  const hide = useCallback(() => {
    timeoutRef.current = setTimeout(() => setOpen(false), 150);
  }, []);

  // Close on outside tap (mobile)
  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node) &&
          btnRef.current && !btnRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [open]);

  return (
    <span
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      <button
        ref={btnRef}
        onClick={(e) => { e.stopPropagation(); updatePos(); setOpen((v) => !v); }}
        aria-label={`What is ${term}?`}
        style={{
          background: "none", border: "none", cursor: "help",
          padding: "0 2px", display: "inline-flex", alignItems: "center",
          color: "var(--color-text-muted)", opacity: 0.5,
          fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)",
          width: 14, height: 14, justifyContent: "center",
          borderRadius: "50%",
          transition: "opacity 0.15s",
        }}
      >
        ?
      </button>
      {open && pos && createPortal(
        <div
          ref={popRef}
          onMouseEnter={() => clearTimeout(timeoutRef.current)}
          onMouseLeave={hide}
          style={{
            position: "fixed",
            left: pos.x,
            top: pos.y,
            transform: "translate(-50%, calc(-100% - 6px))",
            width: 220,
            padding: "var(--space-sm) var(--space-md)",
            background: "var(--color-surface-0)",
            border: "1px solid var(--glass-border)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-elevated)",
            zIndex: 10000,
          }}
        >
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
        </div>,
        document.body,
      )}
    </span>
  );
}
