export function AllocationDonut({ data, size = 180 }: {
  data: { label: string; value: number; color: string }[];
  size?: number;
}) {
  const total = data.reduce((s, d) => s + d.value, 0);
  if (total <= 0) return null;

  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <svg viewBox="0 0 200 200" width={size} height={size}>
      {data.map((d, i) => {
        const pct = d.value / total;
        const dash = pct * circumference;
        const currentOffset = offset;
        offset += dash;
        return (
          <circle
            key={i}
            cx="100" cy="100" r={radius}
            fill="none"
            stroke={d.color}
            strokeWidth="28"
            strokeDasharray={`${dash} ${circumference - dash}`}
            strokeDashoffset={-currentOffset}
            transform="rotate(-90 100 100)"
          />
        );
      })}
      <text x="100" y="95" textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--color-text)">
        {data.length > 0 ? `${((data[0].value / total) * 100).toFixed(0)}%` : ""}
      </text>
      <text x="100" y="112" textAnchor="middle" fontSize="10" fill="var(--color-text-muted)">
        {data.length > 0 ? data[0].label : ""}
      </text>
    </svg>
  );
}
