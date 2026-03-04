export function formatCurrency(n: number): string {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function formatPct(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function pnlColor(n: number): string {
  if (n > 0) return "var(--color-success)";
  if (n < 0) return "var(--color-error)";
  return "var(--color-text-secondary)";
}

export function pnlGradientClass(n: number): string {
  if (n > 0) return "text-gradient-success";
  if (n < 0) return "text-gradient-error";
  return "";
}

export function alertVariant(severity: string): "accent" | "success" | "warning" | "error" | "neutral" {
  const map: Record<string, "accent" | "success" | "warning" | "error" | "neutral"> = {
    info: "accent", warning: "warning", error: "error", critical: "error",
  };
  return map[severity] ?? "neutral";
}
