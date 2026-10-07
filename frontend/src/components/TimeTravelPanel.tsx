"use client";

import { useEffect, useState } from "react";

import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";
import { inr, signColor } from "@/lib/format";

/** Phase 37: view the portfolio as of any past snapshot date. */
export function TimeTravelPanel() {
  const [dates, setDates] = useState<string[]>([]);
  const [date, setDate] = useState<string>("");
  const [snap, setSnap] = useState<Awaited<ReturnType<typeof api.aiTimeTravel>> | null>(null);

  useEffect(() => {
    api
      .aiTimeTravelDates()
      .then((d) => {
        setDates(d);
        if (d.length) setDate(d[Math.floor(d.length / 2)]);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (date) api.aiTimeTravel(date).then(setSnap).catch(() => {});
  }, [date]);

  if (dates.length === 0) return null;

  return (
    <Panel title="Time travel" description="See the portfolio as it was on a past date.">
      <input
        type="range"
        min={0}
        max={dates.length - 1}
        value={Math.max(0, dates.indexOf(date))}
        onChange={(e) => setDate(dates[Number(e.target.value)])}
        className="w-full accent-[var(--primary)]"
        aria-label="Snapshot date"
      />
      {snap ? (
        <div className="mt-3 space-y-2">
          <div className="flex items-baseline gap-3">
            <span className="text-sm text-muted-foreground">As of</span>
            <span className="font-semibold tabular-nums">{snap.as_of}</span>
            <span className="ml-auto text-xl font-semibold tabular-nums">{inr(snap.total_value)}</span>
          </div>
          <div className="text-sm tabular-nums">
            <span className="text-muted-foreground">P&amp;L </span>
            <span className={signColor(snap.pnl)}>{inr(snap.pnl)}</span>
          </div>
          <ul className="mt-1 space-y-1">
            {snap.top.map((h) => (
              <li key={h.symbol} className="flex justify-between text-xs tabular-nums text-muted-foreground">
                <span>{h.symbol}</span>
                <span>{inr(h.value)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Pick a date to travel to.</p>
      )}
    </Panel>
  );
}
