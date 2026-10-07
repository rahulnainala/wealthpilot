"use client";

import { useEffect, useRef, useState } from "react";

import { inrPrecise } from "@/lib/format";
import { sanePrice } from "@/lib/prices";
import { cn } from "@/lib/utils";
import { useTickerStore } from "@/store/useTickerStore";

/** LTP cell that overlays the live tick for a symbol and flashes on change. */
export function LivePrice({
  symbol,
  fallback,
}: {
  symbol: string;
  fallback: number;
}) {
  const tick = useTickerStore((s) => s.ticks[symbol]);
  const price = sanePrice(fallback, tick?.ltp);

  const prev = useRef(price);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (price > prev.current) setFlash("up");
    else if (price < prev.current) setFlash("down");
    prev.current = price;
    const timer = setTimeout(() => setFlash(null), 500);
    return () => clearTimeout(timer);
  }, [price]);

  return (
    <span
      className={cn(
        "rounded px-1 tabular-nums transition-colors duration-300 motion-reduce:transition-none",
        flash === "up" && "bg-gain/20",
        flash === "down" && "bg-loss/20",
      )}
    >
      {inrPrecise(price)}
    </span>
  );
}

/** Read the current live-or-fallback price for a symbol (non-visual). */
export function useLivePrice(symbol: string, fallback: number): number {
  const tick = useTickerStore((s) => s.ticks[symbol]);
  return sanePrice(fallback, tick?.ltp);
}
