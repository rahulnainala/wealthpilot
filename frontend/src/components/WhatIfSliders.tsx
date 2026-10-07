"use client";

import { useEffect, useState } from "react";

import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import type { Goal, GoalSimulation } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Phase 26: drag SIP / target and watch P(success) update live (debounced).
 *
 * Purely exploratory — the goal's *actual* probability is refreshed by
 * GoalCard, so this panel stays collapsed until asked for and nothing on the
 * card depends on it having been opened.
 */
export function WhatIfSliders({ goal }: { goal: Goal }) {
  const [sip, setSip] = useState(goal.monthly_contribution ?? 0);
  const [target, setTarget] = useState(goal.target_value ?? 0);
  const [sim, setSim] = useState<GoalSimulation | null>(null);
  const [busy, setBusy] = useState(false);

  const solvable = Boolean(goal.target_value && goal.target_date);
  const sipMax = Math.max(50_000, Math.round((goal.monthly_contribution || 10_000) * 3));
  const targetBase = goal.target_value || 1_000_000;

  useEffect(() => {
    if (!solvable) return;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const next = await api.simulateGoal(goal.id, {
          monthly_contribution: sip,
          target_value: target,
        });
        setSim(next);
      } catch {
        /* leave last result */
      } finally {
        setBusy(false);
      }
    }, 450);
    return () => clearTimeout(t);
  }, [sip, target, goal.id, solvable]);

  if (!solvable) return null;
  const prob = sim ? Math.round(sim.probability_of_success * 100) : null;
  const tone = prob == null ? "text-muted-foreground" : prob >= 75 ? "text-gain" : prob >= 40 ? "text-warning" : "text-loss";

  return (
    <Panel title="What-if" description="Drag to preview — this doesn't change your goal.">
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="flex justify-between tabular-nums">
            <span className="text-muted-foreground">Monthly SIP</span>
            <span className="font-medium">{inr(sip)}/mo</span>
          </span>
          <input
            type="range"
            min={0}
            max={sipMax}
            step={500}
            value={sip}
            onChange={(e) => setSip(Number(e.target.value))}
            className="mt-1 w-full accent-[var(--primary)]"
            aria-label="Monthly SIP"
          />
        </label>
        <label className="block text-sm">
          <span className="flex justify-between tabular-nums">
            <span className="text-muted-foreground">Target</span>
            <span className="font-medium">{inr(target)}</span>
          </span>
          <input
            type="range"
            min={Math.round(targetBase * 0.5)}
            max={Math.round(targetBase * 2)}
            step={Math.max(1000, Math.round(targetBase / 100))}
            value={target}
            onChange={(e) => setTarget(Number(e.target.value))}
            className="mt-1 w-full accent-[var(--primary)]"
            aria-label="Target value"
          />
        </label>
        <div className="flex items-baseline gap-4 border-t border-border pt-3">
          <span className="text-sm text-muted-foreground">Success odds</span>
          <span className={cn("text-2xl font-semibold tabular-nums", tone)}>
            {busy ? "…" : prob != null ? `${prob}%` : "—"}
          </span>
          <span className="ml-auto text-xs tabular-nums text-muted-foreground">
            median {sim ? inr(sim.median_ending_value) : "—"}
          </span>
        </div>
      </div>
    </Panel>
  );
}
