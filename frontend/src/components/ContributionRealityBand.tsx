"use client";

import { Info } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import type { ContributionReality } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Below this share of the plan, the odds above describe a plan that isn't being funded. */
const MATERIAL_SHORTFALL = 0.75;

/**
 * Modelled SIP against the contributions the holdings history actually shows.
 *
 * Every goal probability on this page is computed from the planned monthly
 * contribution. When real contributions run well under that, a "98% likely"
 * badge is describing an intention rather than a trajectory — so this band
 * states the gap next to the odds instead of leaving them to be read as fact.
 * It is measured from cost basis, which moves only when units are actually
 * bought, so it cannot be flattered by a rising market.
 */
export function ContributionRealityBand() {
  const { data } = useApi<ContributionReality>(() => api.contributionReality(), []);
  if (!data || !data.sufficient_history || data.actual_total == null) return null;
  if (data.planned_total <= 0) return null;

  const ratio = data.actual_total / data.planned_total;
  if (ratio >= MATERIAL_SHORTFALL) return null;

  const funded = Math.max(0, Math.min(100, ratio * 100));

  return (
    <div className="rounded-xl border border-warning/40 bg-warning/[0.06] p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        {/* h2 to match Panel titles: this band is a top-level section of the
            page, a peer of the panels around it, not a child of one. */}
        <h2 className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-warning">
          <Info className="size-3.5" aria-hidden="true" />
          Plan vs actual
        </h2>
        <span className="text-sm tabular-nums">
          <span className="font-semibold">{inr(data.actual_total)}/mo</span>
          <span className="text-muted-foreground">
            {" "}
            going in vs {inr(data.planned_total)}/mo planned
          </span>
        </span>
      </div>

      {/* `Progress` is a plain div with no progressbar role, so an aria-label
          on it is silently dropped — bad ARIA that only looks handled. The
          ratio is stated in the text above and below, so the bar is decorative
          here, matching how the Action Plan uses it. */}
      <Progress
        value={funded}
        aria-hidden="true"
        className="mt-3 h-1.5"
        indicatorClassName="bg-warning motion-reduce:transition-none"
      />

      <p className="mt-2 text-2xs leading-relaxed text-muted-foreground">
        You are contributing{" "}
        <span className="font-medium text-foreground tabular-nums">
          {funded < 1 ? "<1" : funded.toFixed(0)}%
        </span>{" "}
        of the modelled SIP (measured over{" "}
        {/* Under two months, "0.85 months" is both uglier and less honest about
            how short the sample is than saying the day count outright. */}
        <span className="tabular-nums">
          {data.months_observed < 2
            ? `${data.days_observed} days`
            : `${data.months_observed.toFixed(1)} months`}
        </span>{" "}
        of holdings history). The success odds below are computed from the{" "}
        <span className="font-medium text-foreground">planned</span> figure — treat them
        as &ldquo;if funded at plan&rdquo;, not as a forecast of the current pace.
      </p>

      <ul className="mt-3 grid gap-1.5 sm:grid-cols-3">
        {data.goals
          .filter((g) => g.planned_monthly > 0)
          .map((g) => (
            <li
              key={g.key}
              className="flex items-baseline justify-between gap-2 rounded-lg border border-border bg-card/60 px-3 py-2 text-2xs"
            >
              <span className="min-w-0 truncate text-muted-foreground">{g.name}</span>
              <span
                className={cn(
                  "shrink-0 tabular-nums",
                  (g.ratio ?? 0) < MATERIAL_SHORTFALL && "text-warning",
                )}
              >
                {inr(g.actual_monthly ?? 0)} / {inr(g.planned_monthly)}
              </span>
            </li>
          ))}
      </ul>
    </div>
  );
}
