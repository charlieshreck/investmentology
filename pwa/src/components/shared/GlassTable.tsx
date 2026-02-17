interface Column {
  key: string;
  label: string;
  align?: "left" | "center" | "right";
}

interface GlassTableProps {
  columns: Column[];
  data: Record<string, unknown>[];
  onRowClick?: (row: Record<string, unknown>, index: number) => void;
}

export function GlassTable({ columns, data, onRowClick }: GlassTableProps) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: "var(--text-sm)",
        }}
      >
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  textAlign: col.align ?? "left",
                  padding: "var(--space-md) var(--space-lg)",
                  color: "var(--color-text-muted)",
                  fontWeight: 500,
                  fontSize: "var(--text-xs)",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  borderBottom: "1px solid var(--glass-border)",
                  whiteSpace: "nowrap",
                }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={i}
              onClick={() => onRowClick?.(row, i)}
              style={{
                cursor: onRowClick ? "pointer" : "default",
                transition: `background var(--duration-fast) var(--ease-out)`,
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background =
                  "var(--color-surface-1)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = "transparent";
              }}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  style={{
                    textAlign: col.align ?? "left",
                    padding: "var(--space-md) var(--space-lg)",
                    borderBottom: "1px solid var(--glass-border)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {String(row[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
