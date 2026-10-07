"use client";

import { ArrowRight } from "lucide-react";

import { Loadable } from "@/components/Loadable";
import { Panel } from "@/components/Panel";
import { Progress } from "@/components/ui/progress";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { inr, sharePct } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * "Goals at a glance" — the funding waypoints that used to ride the cockpit
 * FlightStrip, promoted into a proper Overview card that pairs with the
 * allocation panel. One row per goal: how funded it is, the odds of hitting it,
 * and the ETA. Full detail (edits, assignments, simulation) lives on the Goals
 * tab; this is the glance, deep-linked there.
 */
export function GoalsGlance() {
  const analyses = useApi(() => api.goalsAnalysis(), []);
  const goals = useApi(() => api.goals(), []);

  const targets = new Map((goals.data ?? []).map((g) => [g.key, g.target_value ?? 0]));

  return (
    <Panel
      title="Goals at a Glance"
      description="Funding progress toward each goal — full detail on the Goals tab."
      action={
        <a
          href="#goals"
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          View all
          <ArrowRight className="size-3" aria-hidden="true" />
        </a>
      }
    >
      <Loadable
        state={analyses}
        skeleton={
          <div className="space-y-4">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-12 animate-pulse rounded-lg bg-muted/40 motion-reduce:animate-none"
              />
            ))}
          </div>
        }
      >
        {(list) =>
          list.length === 0 ? (
            <p className="text-sm text-muted-foreground">No goals configured yet.</p>
          ) : (
            <ul className="space-y-4">
              {list.map((g) => {
                const target = targets.get(g.key) ?? 0;
                const funded = target > 0 ? (g.assigned_value / target) * 100 : 0;
                const prob = g.simulation
                  ? Math.round(g.simulation.probability_of_success * 100)
                  : null;
                const onTrack = prob !== null && prob >= 90;
                return (
                  <li key={g.key}>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="min-w-0 truncate text-sm font-medium">{g.name}</span>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {inr(g.assigned_value)}
                        {target > 0 ? <> / {inr(target)}</> : null}
                      </span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-3">
                      <Progress
                        value={funded}
                        aria-hidden="true"
                        className="h-1.5 flex-1"
                        indicatorClassName={onTrack ? "bg-gain" : "bg-primary"}
                      />
                      <span className="w-11 shrink-0 text-right text-xs font-medium tabular-nums">
                        {sharePct(funded)}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-x-3 text-2xs uppercase tracking-[0.1em] text-muted-foreground">
                      <span className="tabular-nums">
                        <span className={cn("font-semibold", onTrack ? "text-gain" : "text-foreground")}>
                          {prob !== null ? `${prob}%` : "—"}
                        </span>{" "}
                        odds
                      </span>
                      <span aria-hidden="true">·</span>
                      <span className="tabular-nums">
                        ETA {g.months_remaining != null ? `${g.months_remaining}mo` : "—"}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )
        }
      </Loadable>
    </Panel>
  );
}
