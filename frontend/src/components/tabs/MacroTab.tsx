"use client";

import { KpiCard } from "@/components/KpiCard";
import { Panel } from "@/components/Panel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";

function EarningsPanel() {
  const state = useApi(() => api.aiEarnings(), []);
  const rows = state.data ?? [];
  return (
    <Panel title="Earnings ahead" description="Upcoming results for your stocks (best-effort feed).">
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {state.loading ? "Checking the calendar…" : "No upcoming dates found."}
        </p>
      ) : (
        <ul className="space-y-1.5">
          {rows.map((r) => (
            <li key={r.symbol} className="flex justify-between text-sm tabular-nums">
              <span className="font-medium">{r.symbol}</span>
              <span className="text-muted-foreground">{r.earnings_date}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** Phase 36/38: macro indicators + earnings vs the portfolio's energy exposure. */
export function MacroTab() {
  const state = useApi(() => api.aiMacro(), []);
  const m = state.data;

  return (
    <div className="space-y-4">
      {!m ? (
        <Panel title="Macro">
          <p className="text-sm text-muted-foreground">
            {state.loading ? "Fetching macro feed…" : "Macro feed unavailable."}
          </p>
        </Panel>
      ) : (
        <>
          {m.indicators.length === 0 ? (
            <Panel title="Macro">
              <p className="text-sm text-muted-foreground">Macro feed unreachable right now.</p>
            </Panel>
          ) : (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {m.indicators.map((i) => (
                <KpiCard
                  key={i.symbol}
                  title={i.name}
                  value={i.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                  sub={`${i.change_pct >= 0 ? "+" : ""}${i.change_pct.toFixed(2)}%`}
                  subClassName={i.change_pct >= 0 ? "text-gain" : "text-loss"}
                />
              ))}
            </div>
          )}
          <div className="grid items-start gap-4 lg:grid-cols-2">
            <Panel title="What it means for you" description="Macro tied to your exposure.">
              <p className="text-sm">
                PSU-energy exposure:{" "}
                <span className="font-semibold tabular-nums">{m.energy_exposure_pct}%</span>
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{m.note}</p>
            </Panel>
            <EarningsPanel />
          </div>
        </>
      )}
    </div>
  );
}
