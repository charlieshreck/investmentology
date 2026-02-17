import { useEffect, useState } from "react";

type MarketState = "pre-market" | "open" | "after-hours" | "closed";

interface MarketInfo {
  state: MarketState;
  label: string;
  color: string;
}

// NYSE major holidays (month-day format for quick lookup)
const NYSE_HOLIDAYS = new Set([
  "01-01", // New Year's Day
  "01-20", // MLK Day (approx)
  "02-17", // Presidents Day (approx)
  "04-18", // Good Friday (approx)
  "05-26", // Memorial Day (approx)
  "06-19", // Juneteenth
  "07-04", // Independence Day
  "09-01", // Labor Day (approx)
  "11-27", // Thanksgiving (approx)
  "12-25", // Christmas
]);

function getMarketInfo(): MarketInfo {
  const now = new Date();
  // Convert to ET
  const et = new Date(
    now.toLocaleString("en-US", { timeZone: "America/New_York" })
  );
  const day = et.getDay(); // 0=Sun, 6=Sat
  const hours = et.getHours();
  const mins = et.getMinutes();
  const time = hours * 60 + mins;

  // Weekend
  if (day === 0 || day === 6) {
    return { state: "closed", label: "Market Closed", color: "var(--color-text-tertiary)" };
  }

  // Check holidays (rough check)
  const mmdd = `${String(et.getMonth() + 1).padStart(2, "0")}-${String(et.getDate()).padStart(2, "0")}`;
  if (NYSE_HOLIDAYS.has(mmdd)) {
    return { state: "closed", label: "Market Closed (Holiday)", color: "var(--color-text-tertiary)" };
  }

  // Pre-market: 4:00-9:30 ET
  if (time >= 240 && time < 570) {
    return { state: "pre-market", label: "Pre-Market", color: "var(--color-warning)" };
  }

  // Market open: 9:30-16:00 ET
  if (time >= 570 && time < 960) {
    return { state: "open", label: "Market Open", color: "var(--color-success)" };
  }

  // After-hours: 16:00-20:00 ET
  if (time >= 960 && time < 1200) {
    return { state: "after-hours", label: "After-Hours", color: "var(--color-warning)" };
  }

  return { state: "closed", label: "Market Closed", color: "var(--color-text-tertiary)" };
}

export function MarketStatus({ wsStatus }: { wsStatus?: string }) {
  const [info, setInfo] = useState<MarketInfo>(getMarketInfo);

  useEffect(() => {
    const id = setInterval(() => setInfo(getMarketInfo()), 60_000);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        fontSize: "var(--text-xs)",
        color: info.color,
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: info.color,
          display: "inline-block",
          animation: info.state === "open" ? "pulse 2s infinite" : "none",
        }}
      />
      {info.label}
      {wsStatus === "connected" && (
        <span style={{ fontSize: "9px", opacity: 0.6, marginLeft: 2 }}>LIVE</span>
      )}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
