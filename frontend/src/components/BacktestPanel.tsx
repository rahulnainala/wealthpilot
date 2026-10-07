"use client";

import { Panel } from "@/components/Panel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const sign = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

/** Phase 54: backtest the +10% take-profit rule vs buy-and-hold on legacy stocks. */
export function BacktestPanel() {
  const state = useApi(() => api.aiBacktest(), []);
  const d = state.data;
  const hasResults = d && d.results.length > 0;

  return (
    <Panel
      title="Sell-rule backtest"
      description="Would a +10% take-profit have beaten holding the legacy book?"
    >
      {!d ? (
        <p className="text-sm text-muted-foreground">
          {state.loading ? "Replaying price history…" : "No backtest yet."}
        </p>
      ) : !hasResults ? (
        <p className="text-sm text-muted-foreground">
          {d.message ?? "No legacy stocks with price history to backtest."}
        </p>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Take-profit" value={sign(d.avg_rule_return_pct ?? 0)} />
            <Stat label="Buy & hold" value={sign(d.avg_buy_hold_return_pct ?? 0)} />
            <Stat
              label="Edge"
              value={sign(d.avg_edge_pct ?? 0)}
              accent={(d.avg_edge_pct ?? 0) >= 0 ? "text-gain" : "text-loss"}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Rule beat holding on{" "}
            <span className="font-medium text-foreground">
              {d.rule_wins}/{d.count}
            </span>{" "}
            names · {d.triggered_count}/{d.count} hit +{d.threshold_pct}% within {d.window}.
          </p>

          <div className="space-y-1">
            {d.results.map((r) => (
              <div key={r.symbol} className="flex items-center gap-2 text-xs">
                <span className="w-28 shrink-0 truncate" title={r.name}>
                  {r.name}
                </span>
                <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">
                  {sign(r.buy_hold_return_pct)}
                </span>
                <span className="text-muted-foreground">→</span>
                <span className="w-14 shrink-0 text-right tabular-nums">
                  {sign(r.rule_return_pct)}
                </span>
                <span
                  className={cn(
                    "ml-auto w-14 shrink-0 text-right font-medium tabular-nums",
                    r.edge_pct >= 0 ? "text-gain" : "text-loss",
                  )}
                >
                  {sign(r.edge_pct)}
                </span>
              </div>
            ))}
          </div>
          <p className="text-2xs text-muted-foreground">{d.note}</p>
        </div>
      )}
    </Panel>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-2.5">
      <div className="text-2xs text-muted-foreground">{label}</div>
      <div className={cn("mt-0.5 text-lg font-semibold tabular-nums", accent)}>{value}</div>
    </div>
  );
}
