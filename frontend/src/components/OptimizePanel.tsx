"use client";

import { useState } from "react";
import { Scale } from "lucide-react";

import { Panel } from "@/components/Panel";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { inr, sharePct } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Phase 19: risk-parity target allocation + the rebalance to reach it. */
export function OptimizePanel() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.aiOptimize>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [basket, setBasket] = useState<Awaited<ReturnType<typeof api.basketPreview>> | null>(null);

  async function run() {
    if (busy) return;
    setBusy(true);
    try {
      setData(await api.aiOptimize());
      setBasket(await api.basketPreview());
    } finally {
      setBusy(false);
    }
  }

  const current = new Map(data?.current.map((c) => [c.asset_class, c.weight]) ?? []);

  return (
    <Panel
      title="Optimize"
      description="Risk-balanced (inverse-volatility) target allocation — a suggestion to review."
      action={
        <Button variant="outline" size="sm" onClick={() => void run()} disabled={busy}>
          <Scale aria-hidden="true" />
          <span className="hidden sm:inline">{data ? "Recompute" : "Optimize"}</span>
        </Button>
      }
    >
      {busy && !data ? (
        <p className="text-sm text-muted-foreground">Computing a risk-balanced target…</p>
      ) : !data ? (
        <p className="text-sm text-muted-foreground">
          Press Optimize for a risk-parity target allocation and the moves to get there.
        </p>
      ) : (
        <div className="space-y-3">
          <p className="text-sm tabular-nums">
            Estimated volatility{" "}
            <span className="font-semibold text-loss">{data.current_vol_est}%</span> →{" "}
            <span className="font-semibold text-gain">{data.target_vol_est}%</span>
          </p>
          <div className="space-y-1.5">
            {data.rebalance.map((r) => {
              const cur = (current.get(r.asset_class) ?? 0) * 100;
              const tgt = cur + r.delta_weight * 100;
              const up = r.delta_weight >= 0;
              return (
                <div key={r.asset_class} className="text-xs">
                  <div className="flex items-center justify-between tabular-nums">
                    <span className="font-medium capitalize">{r.asset_class}</span>
                    <span className="text-muted-foreground">
                      {sharePct(cur)} → {sharePct(tgt)}{" "}
                      <span className={cn("font-semibold", up ? "text-gain" : "text-loss")}>
                        ({up ? "+" : ""}
                        {inr(r.delta_amount)})
                      </span>
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn("h-full", up ? "bg-gain" : "bg-loss")}
                      style={{ width: `${Math.min(100, tgt)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-2xs text-muted-foreground">
            {data.method} · correlation-agnostic estimate · not an executed trade.
          </p>
          {basket && basket.trims.length > 0 ? (
            <div className="mt-2 border-t border-border pt-2">
              <p className="mb-1 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Trim basket
              </p>
              <ul className="space-y-0.5">
                {basket.trims.slice(0, 6).map((t, i) => (
                  <li key={i} className="flex justify-between text-2xs tabular-nums text-muted-foreground">
                    <span>{t.symbol}</span>
                    <span className="text-loss">−{inr(t.reduce_by)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-2xs text-muted-foreground">{basket.message}</p>
            </div>
          ) : null}
        </div>
      )}
    </Panel>
  );
}
