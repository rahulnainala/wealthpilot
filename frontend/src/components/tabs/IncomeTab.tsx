"use client";

import { Panel } from "@/components/Panel";
import { useApi } from "@/hooks/useApi";
import { SELL_THRESHOLD_PCT, WINDOW_END_LABEL } from "@/lib/exitPlan";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";

/** Phase 34: dividend income forecast (assumed yield).
 *
 * These are legacy PSU/energy/REIT holdings on a sell-off plan (+10% profit
 * exit each, hard-exit by WINDOW_END_LABEL), not a strategy being grown — see the
 * decision journal for why. Expect this number to shrink toward zero, not climb. */
export function IncomeTab() {
  const state = useApi(() => api.aiDividends(), []);
  const d = state.data;

  return (
    <div className="grid items-start gap-4 lg:grid-cols-2">
      <Panel
        title="Dividend income"
        description="Legacy holdings being sold off, not a strategy — see below."
      >
        {!d ? (
          <p className="text-sm text-muted-foreground">
            {state.loading ? "Estimating…" : "No dividend-bucket holdings."}
          </p>
        ) : (
          <div className="space-y-3">
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-semibold tabular-nums text-gain">{inr(d.annual_income)}</span>
              <span className="text-sm text-muted-foreground">/ year</span>
            </div>
            <div className="text-sm tabular-nums text-muted-foreground">
              ~{inr(d.monthly_avg)}/mo average · assumed {d.assumed_yield_pct}% yield
            </div>
            <p className="text-2xs text-muted-foreground">{d.note}</p>
            <p className="rounded-lg border border-warning/40 bg-warning/[0.08] px-3 py-2 text-2xs text-foreground">
              <span className="font-semibold text-warning">Wind-down, not a plan.</span> This basket is on
              the sell-off list — each name exits at +{SELL_THRESHOLD_PCT}% profit, hard-exit by {WINDOW_END_LABEL}, proceeds routed
              50/30/20 into Travel/Vehicle/Emergency (FI is paused until 2030). Dividends are taxed at slab rate every year for a
              PSU/energy/REIT position that isn&apos;t outperforming; growing it further didn&apos;t
              pencil out (a meaningful dividend income would need a large sum parked here). Expect this number to fall,
              not climb.
            </p>
          </div>
        )}
      </Panel>

      <Panel title="By holding" description="Where the income comes from.">
        {!d || d.holdings.length === 0 ? (
          <p className="text-sm text-muted-foreground">No dividend holdings to list.</p>
        ) : (
          <ul className="space-y-1.5">
            {d.holdings.map((h) => (
              <li key={h.symbol} className="flex justify-between text-sm tabular-nums">
                <span className="font-medium">{h.symbol}</span>
                <span className="text-gain">{inr(h.annual)}/yr</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
