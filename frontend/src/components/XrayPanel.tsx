"use client";

import { Panel } from "@/components/Panel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { inr, sharePct } from "@/lib/format";

/** Phase 33: true asset-class exposure — direct stocks vs via-funds. */
export function XrayPanel() {
  const state = useApi(() => api.aiXray(), []);
  const data = state.data;

  return (
    <Panel title="Portfolio X-ray" description="True asset-class exposure — direct vs inside your funds.">
      {!data ? (
        <p className="text-sm text-muted-foreground">
          {state.loading ? "Looking through your funds…" : "No snapshot yet."}
        </p>
      ) : (
        <div className="space-y-3">
          {data.classes.map((c) => {
            const directPct = c.total ? (c.direct / c.total) * 100 : 0;
            return (
              <div key={c.asset_class}>
                <div className="flex justify-between text-xs tabular-nums">
                  <span className="font-medium capitalize">{c.asset_class}</span>
                  <span className="text-muted-foreground">
                    {sharePct(c.weight * 100)} · {inr(c.total)}
                  </span>
                </div>
                <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${directPct}%` }} title={`Direct ${inr(c.direct)}`} />
                  <div className="h-full bg-primary/40" style={{ width: `${100 - directPct}%` }} title={`Funds ${inr(c.fund)}`} />
                </div>
              </div>
            );
          })}
          <p className="flex gap-4 text-2xs text-muted-foreground">
            <span className="flex items-center gap-1"><span className="size-2 rounded-sm bg-primary" /> Direct</span>
            <span className="flex items-center gap-1"><span className="size-2 rounded-sm bg-primary/40" /> Via funds</span>
          </p>
        </div>
      )}
    </Panel>
  );
}
