"use client";

import { useEffect } from "react";

import { WS_BASE } from "@/lib/config";
import { type Tick, useTickerStore } from "@/store/useTickerStore";

/** Subscribe to /ws/ticks, feeding the ticker store with exponential-backoff reconnect. */
export function useTicks(enabled = true): void {
  const applyTick = useTickerStore((s) => s.applyTick);
  const setStreamStatus = useTickerStore((s) => s.setStreamStatus);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    let socket: WebSocket | null = null;
    let closedByUs = false;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      socket = new WebSocket(`${WS_BASE}/ws/ticks`);

      socket.onopen = () => {
        attempt = 0;
        setStreamStatus("live");
      };
      socket.onmessage = (event) => {
        try {
          applyTick(JSON.parse(event.data) as Tick);
        } catch {
          /* ignore malformed frame */
        }
      };
      socket.onclose = () => {
        if (closedByUs) return;
        setStreamStatus("snapshot");
        attempt += 1;
        const delay = Math.min(30_000, 1_000 * 2 ** attempt);
        timer = setTimeout(connect, delay);
      };
      socket.onerror = () => socket?.close();
    };

    connect();

    return () => {
      closedByUs = true;
      if (timer) clearTimeout(timer);
      socket?.close();
      setStreamStatus("snapshot");
    };
  }, [enabled, applyTick, setStreamStatus]);
}
