import { Skeleton } from "./Skeleton";

export function MetricCardSkeleton() {
  return (
    <div
      style={{
        background: "var(--glass-bg)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-lg)",
        border: "1px solid var(--glass-border)",
      }}
    >
      <Skeleton width="60%" height={12} />
      <div style={{ height: 8 }} />
      <Skeleton width="40%" height={24} />
    </div>
  );
}

export function PositionRowSkeleton() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "var(--space-md) 0",
        borderBottom: "1px solid var(--glass-border)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Skeleton width={60} height={14} />
        <Skeleton width={100} height={10} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
        <Skeleton width={70} height={14} />
        <Skeleton width={50} height={10} />
      </div>
    </div>
  );
}

export function RecommendationCardSkeleton() {
  return (
    <div
      style={{
        background: "var(--glass-bg)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-lg)",
        border: "1px solid var(--glass-border)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-md)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Skeleton width={80} height={16} />
        <Skeleton width={50} height={20} />
      </div>
      <Skeleton lines={2} height={12} />
      <div style={{ display: "flex", gap: "var(--space-sm)" }}>
        <Skeleton width={60} height={20} />
        <Skeleton width={60} height={20} />
        <Skeleton width={60} height={20} />
      </div>
    </div>
  );
}
