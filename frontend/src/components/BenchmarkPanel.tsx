"use client";

import { LineChart } from "lucide-react";

import { Panel } from "@/components/Panel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Phase 21: how the portfolio's recent return compares with NIFTY 50. */
export function BenchmarkPanel() {
  const state = useApi(() => api.aiBenchmark(), []);
  const b = state.data;

  return (
    <Panel title="Vs NIFTY 50" description="Recent return against the index the plan assumes.">
      {!b ? (
        <p className="text-sm text-muted-foreground">
          {state.loading ? "Comparing…" : "Not enough history (or NIFTY data) to benchmark yet."}
        </p>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <LineChart
              className={cn("size-4", b.alpha_pct >= 0 ? "text-gain" : "text-loss")}
              aria-hidden="true"
            />
            <span className="text-lg font-semibold tabular-nums">
              {b.alpha_pct >= 0 ? "+" : ""}
              {b.alpha_pct.toFixed(1)} pts
            </span>
            <span className="text-xs text-muted-foreground">
              {b.alpha_pct >= 0 ? "ahead of" : "behind"} the index
            </span>
          </div>
          <div className="flex gap-6 text-sm tabular-nums">
            <span>
              Portfolio{" "}
              <span className={cn("font-semibold", b.portfolio_return_pct >= 0 ? "text-gain" : "text-loss")}>
                {b.portfolio_return_pct >= 0 ? "+" : ""}
                {b.portfolio_return_pct.toFixed(1)}%
              </span>
            </span>
            <span>
              NIFTY{" "}
              <span className={cn("font-semibold", b.nifty_return_pct >= 0 ? "text-gain" : "text-loss")}>
                {b.nifty_return_pct >= 0 ? "+" : ""}
                {b.nifty_return_pct.toFixed(1)}%
              </span>
            </span>
          </div>
          <p className="text-2xs text-muted-foreground">{b.note}</p>
        </div>
      )}
    </Panel>
  );
}
