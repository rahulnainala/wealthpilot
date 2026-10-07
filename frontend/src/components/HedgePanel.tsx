"use client";

import { Panel } from "@/components/Panel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";

/** Phase 51: protective-put hedge sizing (heuristic). */
export function HedgePanel() {
  const state = useApi(() => api.aiHedge(), []);
  const h = state.data;

  return (
    <Panel title="Hedge" description="Protective-put sizing for your equity exposure.">
      {!h ? (
        <p className="text-sm text-muted-foreground">
          {state.loading ? "Sizing a hedge…" : "No snapshot yet."}
        </p>
      ) : h.nifty_put_lots != null ? (
        <div className="space-y-2">
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-semibold tabular-nums">{h.nifty_put_lots}</span>
            <span className="text-sm text-muted-foreground">NIFTY put lot(s)</span>
            <span className="ml-auto text-sm tabular-nums">
              ≈ <span className="font-semibold text-loss">{inr(h.est_premium_cost ?? 0)}</span> premium
            </span>
          </div>
          <p className="text-xs tabular-nums text-muted-foreground">
            Hedging {inr(h.equity_exposure)} equity-like · NIFTY {h.nifty_spot?.toLocaleString("en-IN")}
          </p>
          <p className="text-2xs text-muted-foreground">{h.note}</p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{h.message ?? "No equity exposure to hedge."}</p>
      )}
    </Panel>
  );
}
