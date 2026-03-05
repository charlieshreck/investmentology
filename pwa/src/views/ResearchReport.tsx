import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";

interface ReportSection {
  title: string;
  content: string;
}

interface Report {
  ticker: string;
  name: string;
  sector: string;
  industry: string;
  generated_at: string;
  sections: ReportSection[];
  error?: string;
}

/** Render simple markdown content as React elements (no dangerouslySetInnerHTML). */
function MarkdownContent({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Table header row
    if (line.startsWith("|") && i + 1 < lines.length && lines[i + 1].includes("---")) {
      // Collect table rows
      const headers = line.split("|").filter(Boolean).map((c) => c.trim());
      const rows: string[][] = [];
      let j = i + 2; // skip separator
      while (j < lines.length && lines[j].startsWith("|")) {
        rows.push(lines[j].split("|").filter(Boolean).map((c) => c.trim()));
        j++;
      }
      elements.push(
        <div key={i} style={{ overflowX: "auto", marginBottom: "var(--space-sm)" }}>
          <table style={{ width: "100%", fontSize: 11, fontFamily: "var(--font-mono)", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {headers.map((h, hi) => (
                  <th key={hi} style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--color-surface-2)", color: "var(--color-text-muted)", fontWeight: 600 }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => (
                    <td key={ci} style={{ padding: "4px 8px", borderBottom: "1px solid var(--color-surface-2)" }}>
                      <BoldText text={cell} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      i = j - 1; // skip processed rows
      continue;
    }

    // Skip table separator rows
    if (line.match(/^\|[-|: ]+\|$/)) continue;

    // Empty line = paragraph break
    if (!line.trim()) {
      elements.push(<div key={i} style={{ height: "var(--space-sm)" }} />);
      continue;
    }

    // Regular line with bold support
    elements.push(
      <p key={i} style={{ margin: "2px 0", lineHeight: 1.7 }}>
        <BoldText text={line} />
      </p>,
    );
  }

  return <>{elements}</>;
}

/** Render text with **bold** markers as <strong> elements. */
function BoldText({ text }: { text: string }) {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <strong key={i} style={{ color: "var(--color-text)" }}>{part}</strong>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export function ResearchReport() {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState(0);

  const goBack = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate("/");
    }
  }, [navigate]);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    fetch(`/api/invest/stock/${ticker}/report`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => setReport(data))
      .catch((err) => {
        setReport({ ticker: ticker.toUpperCase(), name: "", sector: "", industry: "", generated_at: "", sections: [], error: err.message || "Failed to load report" });
      })
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) {
    return (
      <div style={{ padding: "var(--space-xl)", maxWidth: 900, margin: "0 auto" }}>
        <div className="skeleton" style={{ height: 40, width: 300, borderRadius: "var(--radius-sm)", marginBottom: "var(--space-lg)" }} />
        {[1, 2, 3].map((i) => (
          <div key={i} className="skeleton" style={{ height: 120, borderRadius: "var(--radius-md)", marginBottom: "var(--space-md)" }} />
        ))}
      </div>
    );
  }

  if (!report || report.error) {
    return (
      <div style={{ padding: "var(--space-xl)", textAlign: "center", color: "var(--color-text-muted)" }}>
        <p style={{ fontSize: "var(--text-lg)", marginBottom: "var(--space-md)" }}>
          {report?.error || "Report unavailable"}
        </p>
        <button
          onClick={goBack}
          style={{
            padding: "8px 20px",
            background: "var(--color-accent)",
            color: "#fff",
            border: "none",
            borderRadius: "var(--radius-md)",
            cursor: "pointer",
            fontSize: "var(--text-sm)",
          }}
        >
          Go Back
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: "var(--space-lg)", padding: "var(--space-lg)", maxWidth: 1100, margin: "0 auto" }}>
      {/* TOC sidebar — desktop only */}
      <nav className="report-toc" style={{ position: "sticky", top: "var(--space-lg)", alignSelf: "flex-start", minWidth: 180, display: "none" }}>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "var(--space-sm)" }}>
          Contents
        </div>
        {report.sections.map((s, i) => (
          <button
            key={i}
            onClick={() => {
              setActiveSection(i);
              document.getElementById(`section-${i}`)?.scrollIntoView({ behavior: "smooth" });
            }}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "6px 12px",
              fontSize: 12,
              color: activeSection === i ? "var(--color-accent-bright)" : "var(--color-text-muted)",
              background: activeSection === i ? "var(--color-accent-ghost)" : "transparent",
              border: "none",
              borderRadius: "var(--radius-sm)",
              cursor: "pointer",
              fontFamily: "var(--font-mono)",
              marginBottom: 2,
            }}
          >
            {s.title}
          </button>
        ))}
      </nav>

      {/* Main content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header */}
        <div style={{ marginBottom: "var(--space-xl)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: "var(--space-sm)" }}>
            <button
              onClick={goBack}
              style={{
                background: "var(--color-surface-1)",
                border: "1px solid var(--color-surface-2)",
                borderRadius: "var(--radius-sm)",
                padding: "4px 10px",
                color: "var(--color-text-muted)",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              Back
            </button>
            <button
              onClick={() => window.print()}
              style={{
                background: "var(--color-surface-1)",
                border: "1px solid var(--color-surface-2)",
                borderRadius: "var(--radius-sm)",
                padding: "4px 10px",
                color: "var(--color-text-muted)",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              Print / PDF
            </button>
          </div>
          <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, color: "var(--color-text)", margin: 0 }}>
            {report.name}
          </h1>
          <div style={{ display: "flex", gap: "var(--space-sm)", marginTop: "var(--space-xs)", fontSize: "var(--text-sm)", color: "var(--color-text-muted)", flexWrap: "wrap" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--color-accent-bright)" }}>{report.ticker}</span>
            <span>{report.sector}</span>
            <span>{report.industry}</span>
            <span>Generated {new Date(report.generated_at).toLocaleDateString()}</span>
          </div>
        </div>

        {/* Sections */}
        {report.sections.map((section, i) => (
          <section
            key={i}
            id={`section-${i}`}
            style={{
              background: "var(--color-surface-0)",
              border: "1px solid var(--color-surface-2)",
              borderRadius: "var(--radius-lg)",
              padding: "var(--space-lg)",
              marginBottom: "var(--space-md)",
            }}
          >
            <h2 style={{
              fontSize: "var(--text-lg)",
              fontWeight: 700,
              color: "var(--color-text)",
              marginTop: 0,
              marginBottom: "var(--space-md)",
              paddingBottom: "var(--space-sm)",
              borderBottom: "1px solid var(--color-surface-2)",
            }}>
              {section.title}
            </h2>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
              <MarkdownContent content={section.content} />
            </div>
          </section>
        ))}
      </div>

      <style>{`
        @media (min-width: 768px) {
          .report-toc { display: block !important; }
        }
        @media print {
          .report-toc { display: none !important; }
          section { break-inside: avoid; }
        }
      `}</style>
    </div>
  );
}
