"use client";

import { useState } from "react";
import { Scale, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import { probabilityColor } from "@/lib/severity";
import { cn } from "@/lib/utils";

type Allocation = {
  goal_id: number;
  goal_key: string;
  goal_name: string;
  allocated_monthly: number;
  baseline_probability: number;
  optimized_probability: number;
};

type Result = {
  total_budget: number;
  step: number;
  allocations: Allocation[];
  expected_goals_before: number;
  expected_goals_after: number;
  on_track_after: number;
  goal_count: number;
  unallocated: number;
};

/** Budget range shared with the Basket tab's routing preview (₹10k–₹2L). */
const BUDGET_MIN = 10_000;
const BUDGET_MAX = 200_000;
const BUDGET_STEP = 1_000;

/**
 * Phase 53: split one monthly budget across every goal, weakest-goal-first.
 *
 * Opens on `planned` — the actual SIP total from the goals — rather than a
 * round guess, so the first result answers "what would my real budget do if I
 * let the optimizer place it" instead of describing someone else's budget.
 */
export function JointOptimizePanel({ planned }: { planned: number }) {
  const [budget, setBudget] = useState(planned > 0 ? planned : 20_000);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  async function optimize() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.optimizeGoals(budget));
    } catch {
      setError("Couldn't optimize — need at least one goal with a target value and date.");
    } finally {
      setBusy(false);
    }
  }

  const lift = result
    ? result.expected_goals_after - result.expected_goals_before
    : 0;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Scale className="size-[18px]" />
          </div>
          <div>
            <h3 className="font-semibold leading-tight">Split my budget across goals</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              One monthly pot, allocated where each rupee lifts success odds most.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-2">
        <div>
          <label className="text-xs font-medium text-muted-foreground">
            Total monthly budget
          </label>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="text-sm text-muted-foreground">₹</span>
            <Input
              type="number"
              min={BUDGET_MIN}
              max={BUDGET_MAX}
              step={BUDGET_STEP}
              value={budget}
              onChange={(e) => {
                const n = Number(e.target.value);
                if (!Number.isNaN(n)) setBudget(Math.min(BUDGET_MAX, Math.max(BUDGET_MIN, n)));
              }}
              className="w-40 tabular-nums"
            />
          </div>
        </div>
        <Button onClick={optimize} disabled={busy || budget <= 0} size="sm">
          <Wand2 className={busy ? "animate-spin" : ""} />
          Optimize
        </Button>
      </div>

      <input
        type="range"
        min={BUDGET_MIN}
        max={BUDGET_MAX}
        step={BUDGET_STEP}
        value={budget}
        onChange={(e) => setBudget(Number(e.target.value))}
        className="mt-3 w-full accent-[var(--primary)]"
        aria-label="Total monthly budget"
      />
      <div className="flex justify-between text-2xs tabular-nums text-muted-foreground">
        <span>{inr(BUDGET_MIN)}</span>
        <span>
          {budget === planned ? "your plan" : `plan ${inr(planned)}`}
        </span>
        <span>{inr(BUDGET_MAX)}</span>
      </div>
      <p className="mt-2 text-2xs text-muted-foreground">
        Places money where it lifts odds most — can differ from your fixed 50/30/20 split (see{" "}
        <a href="#basket" className="font-medium text-foreground underline underline-offset-2">
          Basket
        </a>
        ). Doesn&apos;t change your goals.
      </p>

      {error ? <p className="mt-3 text-sm text-loss">{error}</p> : null}

      {result ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
            <span className="font-semibold tabular-nums text-gain">
              {result.on_track_after} of {result.goal_count}
            </span>{" "}
            goals on track ·{" "}
            <span className="text-muted-foreground">
              expected goals met {result.expected_goals_before.toFixed(1)} →{" "}
              <span className="font-medium text-foreground">
                {result.expected_goals_after.toFixed(1)}
              </span>
            </span>
            {lift > 0.05 ? (
              <span className="ml-1 text-gain">(+{lift.toFixed(1)})</span>
            ) : null}
            {result.unallocated > 0 ? (
              <span className="ml-2 text-muted-foreground">
                · {inr(result.unallocated)}/mo left over
              </span>
            ) : null}
          </div>

          <div className="space-y-1.5">
            {result.allocations.map((a) => {
              const share = result.total_budget
                ? (a.allocated_monthly / result.total_budget) * 100
                : 0;
              return (
                <div key={a.goal_id} className="flex items-center gap-2">
                  <span className="w-32 shrink-0 truncate text-xs" title={a.goal_name}>
                    {a.goal_name}
                  </span>
                  <div className="h-2 flex-1 rounded-full bg-muted">
                    <div
                      className="h-2 rounded-full bg-primary"
                      style={{ width: `${Math.max(2, share)}%` }}
                    />
                  </div>
                  <span className="w-24 shrink-0 text-right text-xs font-medium tabular-nums">
                    {inr(a.allocated_monthly)}/mo
                  </span>
                  <span
                    className={cn(
                      "w-16 shrink-0 text-right text-xs tabular-nums",
                      probabilityColor(a.optimized_probability),
                    )}
                  >
                    {(a.baseline_probability * 100).toFixed(0)}→
                    {(a.optimized_probability * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-muted-foreground">
            Each {inr(result.step)} step goes where it lifts success probability the
            most — the biggest expected gain per rupee, not equal shares. Monte Carlo
            estimate.
          </p>
        </div>
      ) : null}
    </div>
  );
}
