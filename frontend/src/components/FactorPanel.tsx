"use client";

import { Panel } from "@/components/Panel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const LABELS: Record<string, string> = {
  value: "Value",
  momentum: "Momentum",
  quality: "Quality",
  size: "Size",
};

/** Phase 55: heuristic value/momentum/quality/size factor tilts. */
export function FactorPanel() {
  const state = useApi(() => api.aiFactors(), []);
  const d = state.data;
  const hasFactors = d && d.factors.length > 0;

  return (
    <Panel title="Factor tilts" description="Value / momentum / quality / size, value-weighted.">
      {!d ? (
        <p className="text-sm text-muted-foreground">
          {state.loading ? "Decomposing holdings…" : "No decomposition yet."}
        </p>
      ) : !hasFactors ? (
        <p className="text-sm text-muted-foreground">{d.message ?? "No holdings to decompose."}</p>
      ) : (
        <div className="space-y-3">
          {d.factors.map((f) => {
            const pos = f.exposure >= 0;
            // Centre line at 50%; bar grows out toward the sign, clamped at ±1.
            const width = Math.min(50, Math.abs(f.exposure) * 50);
            return (
              <div key={f.factor}>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-sm font-medium">{LABELS[f.factor] ?? f.factor}</span>
                  <span className="text-xs text-muted-foreground">{f.tilt}</span>
                </div>
                <div className="relative h-2.5 rounded-full bg-muted">
                  <div className="absolute left-1/2 top-0 h-2.5 w-px bg-border" />
                  <div
                    className={cn(
                      "absolute top-0 h-2.5",
                      pos ? "left-1/2 rounded-r-full bg-primary" : "right-1/2 rounded-l-full bg-amber-500",
                    )}
                    style={{ width: `${width}%` }}
                  />
                </div>
                {f.top_contributors.length > 0 ? (
                  <p className="mt-1 truncate text-2xs text-muted-foreground">
                    {f.top_contributors.map((c) => c.name).join(" · ")}
                  </p>
                ) : null}
              </div>
            );
          })}
          <p className="text-2xs text-muted-foreground">{d.note}</p>
        </div>
      )}
    </Panel>
  );
}
