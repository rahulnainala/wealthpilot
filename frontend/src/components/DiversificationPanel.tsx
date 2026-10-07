"use client";

import { AskAI } from "@/components/AskAI";
import { Loadable } from "@/components/Loadable";
import { Panel } from "@/components/Panel";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Diversification } from "@/lib/types";

function corrColor(c: number): string {
  if (c >= 0.6) return "var(--loss)"; // moves together
  if (c >= 0.3) return "var(--warning)";
  if (c >= 0) return "var(--muted-foreground)";
  return "var(--gain)"; // offsetting
}

function Stat({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: string;
  hint: string;
  className?: string;
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("text-xl font-semibold tabular-nums", className)}>{value}</div>
      <div className="text-xs text-muted-foreground">{hint}</div>
    </div>
  );
}

export function DiversificationPanel() {
  const state = useApi<Diversification>(() => api.diversification(), []);

  return (
    <Panel
      title="Diversification"
      action={<AskAI tip="Explain diversification" question="Explain my diversification — effective holdings, ratio, and the most correlated pairs — and what one change would improve it most." />}
      description="Correlation-based — how independently your holdings actually move (C++ engine)."
    >
      <Loadable state={state} skeleton={<Skeleton className="h-32 w-full" />}>
        {(d) => {
          const concentration = d.holdings ? d.effective_holdings / d.holdings : 0;
          const effClass =
            concentration < 0.4 ? "text-loss" : concentration < 0.6 ? "text-warning" : "";
          const ratioClass =
            d.diversification_ratio < 1.15
              ? "text-loss"
              : d.diversification_ratio < 1.35
                ? "text-warning"
                : "text-gain";
          return (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <Stat
                  label="Effective holdings"
                  value={`${d.effective_holdings} / ${d.holdings}`}
                  hint="independent bets"
                  className={effClass}
                />
                <Stat
                  label="Diversification ratio"
                  value={d.diversification_ratio.toFixed(2)}
                  hint="1.0 = none · higher better"
                  className={ratioClass}
                />
                <Stat
                  label="Avg correlation"
                  value={d.average_correlation.toFixed(2)}
                  hint="lower is better"
                />
              </div>

              {d.top_pairs.length > 0 ? (
                <div className="space-y-1.5">
                  <div className="text-xs font-medium text-muted-foreground">
                    Most correlated pairs
                  </div>
                  {d.top_pairs.map((p) => (
                    <div
                      key={`${p.label_a}-${p.label_b}`}
                      className="flex items-center gap-2"
                    >
                      <span className="w-28 shrink-0 truncate text-xs sm:w-40">
                        {p.label_a} ↔ {p.label_b}
                      </span>
                      <div className="h-2 flex-1 rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full"
                          style={{
                            width: `${Math.abs(p.correlation) * 100}%`,
                            background: corrColor(p.correlation),
                          }}
                        />
                      </div>
                      <span className="w-10 shrink-0 text-right text-xs tabular-nums">
                        {p.correlation.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}

              <p className="text-xs text-muted-foreground">
                Effective holdings is how many <em>independent</em> bets you really have
                (1/HHI of weights). A low ratio + high correlation means a cluster that
                sinks or swims together — trimming it is where diversifying helps most.
              </p>
            </div>
          );
        }}
      </Loadable>
    </Panel>
  );
}
