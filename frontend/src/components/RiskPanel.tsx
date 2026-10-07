"use client";

import { AskAI } from "@/components/AskAI";
import { Loadable } from "@/components/Loadable";
import { Panel } from "@/components/Panel";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { bucketColor, bucketLabel } from "@/lib/buckets";
import { inr } from "@/lib/format";
import type { PortfolioRisk } from "@/lib/types";

export function RiskPanel() {
  const state = useApi<PortfolioRisk>(() => api.portfolioRisk(), []);

  return (
    <Panel
      title="Portfolio Risk"
      action={<AskAI tip="Explain my risk" question="Explain my current portfolio risk — VaR, CVaR, volatility and max drawdown — in plain language, and what drives it." />}
      description="Historical VaR/CVaR from ~3 months of daily NSE returns, computed by the C++ engine."
    >
      <Loadable state={state} skeleton={<Skeleton className="h-32 w-full" />}>
        {(risk) => {
          const maxContribution = Math.max(
            ...risk.contributions.map((c) => Math.abs(c.contribution)),
            1,
          );
          return (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-muted-foreground">1-day VaR (95%)</div>
                  <div className="text-xl font-semibold text-loss tabular-nums">
                    {inr(risk.var)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">CVaR (95%)</div>
                  <div className="text-xl font-semibold text-loss tabular-nums">
                    {inr(risk.cvar)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Annualized volatility</div>
                  <div className="text-xl font-semibold tabular-nums">
                    {(risk.annual_volatility * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Max drawdown (3mo)</div>
                  <div className="text-xl font-semibold text-loss tabular-nums">
                    −{(risk.max_drawdown * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="text-xs font-medium text-muted-foreground">
                  Risk contribution by bucket
                </div>
                {risk.contributions.map((c) => (
                  <div key={c.bucket} className="flex items-center gap-2">
                    <span className="w-24 shrink-0 text-xs">{bucketLabel(c.bucket)}</span>
                    <div className="h-2 flex-1 rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full"
                        style={{
                          width: `${(Math.abs(c.contribution) / maxContribution) * 100}%`,
                          background: bucketColor(c.bucket),
                        }}
                      />
                    </div>
                    <span className="w-20 shrink-0 text-right text-xs tabular-nums">
                      {inr(c.contribution)}
                    </span>
                  </div>
                ))}
              </div>

              <p className="text-xs text-muted-foreground">
                VaR = the 1-day loss you&apos;d exceed only 5% of the time. CVaR = the
                average loss on those worst 5% of days. Fund series are modeled (no free
                NAV history).
              </p>
            </div>
          );
        }}
      </Loadable>
    </Panel>
  );
}
