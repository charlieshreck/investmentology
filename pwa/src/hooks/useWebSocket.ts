import { useEffect, useRef, useState, useCallback } from "react";

export interface PriceUpdate {
  price: number;
  change: number;
  changePct: number;
}

type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

interface UseWebSocketOptions {
  enabled?: boolean;
  onPriceUpdate?: (ticker: string, data: PriceUpdate) => void;
}

export function useWebSocket({ enabled = true, onPriceUpdate }: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const callbackRef = useRef(onPriceUpdate);
  callbackRef.current = onPriceUpdate;

  const connect = useCallback(() => {
    if (!enabled) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/invest/ws/prices`);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      setStatus("connected");
      retryRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "init" || msg.type === "update") {
          const incoming = msg.prices as Record<string, PriceUpdate>;
          setPrices((prev) => ({ ...prev, ...incoming }));

          for (const [ticker, data] of Object.entries(incoming)) {
            callbackRef.current?.(ticker, data);
          }
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (!enabled) {
        setStatus("disconnected");
        return;
      }

      setStatus("reconnecting");
      const delay = Math.min(1000 * 2 ** retryRef.current, 30000);
      retryRef.current++;
      timerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [enabled]);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on unmount
        wsRef.current.close();
        wsRef.current = null;
      }
      setStatus("disconnected");
    };
  }, [connect]);

  return { status, prices };
}
