"use client";

import * as React from "react";
import { useCallback, useState } from "react";
import {
  CalendarClock,
  RefreshCw,
  Settings2,
  ShieldAlert,
  SlidersHorizontal,
  Target,
  Wand2,
} from "lucide-react";

import { AskAI } from "@/components/AskAI";
import { JointOptimizePanel } from "@/components/JointOptimizePanel";
import { Phase0Card } from "@/components/Phase0Card";
import { ContributionRealityBand } from "@/components/ContributionRealityBand";
import { PageHeader } from "@/components/PageHeader";
import { SimRangeBar } from "@/components/SimRangeBar";
import { WhatIfSliders } from "@/components/WhatIfSliders";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { BUCKETS } from "@/lib/buckets";
import { dateOnly, inr, sharePct } from "@/lib/format";
import { PLANNING_INFLATION, inTodaysMoney } from "@/lib/inflation";
import { probabilityColor, severityVariant } from "@/lib/severity";
import { cn } from "@/lib/utils";
import type {
  Goal,
  GoalAnalysis,
  GoalSimulation,
  RequiredContribution,
  Snapshot,
  StressTest,
} from "@/lib/types";

const BUCKET_OPTIONS = ["growth", "dividend", "mf", "other"];
const ON_TRACK = 0.75;

/**
 * Financial Independence is deliberately not a card here.
 *
 * It's a 2040 projection against a placeholder target, not a dated milestone
 * like the other three — and it has a whole tab of its own (Retirement) that
 * models it properly with inflation and a safe-withdrawal rate. Rendering it
 * alongside Travel/Vehicle/Emergency meant a permanent 0% sitting next to goals
 * that are genuinely on track, which read as failure rather than "long game,
 * funded last on purpose".
 *
 * The goal record itself stays — Basket's sleeve (held positions, paused
 * until 2030 per the plan) still resolves through it.
 */
const HIDDEN_GOAL_KEYS = new Set(["fi"]);

interface MfOption {
  isin: string;
  name: string;
}

interface GoalTotals {
  count: number;
  totalTarget: number;
  totalSaved: number;
  onTrack: number;
  offTrack: string[];
  overall: number;
  allTracking: boolean;
}

/** Roll up the visible goals for the header stats and the progress band. Reads
 *  live re-runs (freshSims) first so the on-track count matches the cards. */
function goalTotals(
  analyses: GoalAnalysis[],
  goalByKey: Map<string, Goal>,
  freshSims: Map<string, GoalSimulation>,
): GoalTotals {
  let totalTarget = 0;
  let totalSaved = 0;
  let onTrack = 0;
  const offTrack: string[] = [];
  for (const a of analyses) {
    totalTarget += goalByKey.get(a.key)?.target_value ?? 0;
    totalSaved += a.assigned_value;
    const sim = freshSims.get(a.key) ?? a.simulation;
    if ((sim?.probability_of_success ?? 0) >= ON_TRACK) onTrack += 1;
    else offTrack.push(a.name);
  }
  return {
    count: analyses.length,
    totalTarget,
    totalSaved,
    onTrack,
    offTrack,
    overall: totalTarget ? (totalSaved / totalTarget) * 100 : 0,
    allTracking: onTrack === analyses.length,
  };
}

/** The saved-of-target progress band. The headline figures moved up into the
 *  PageHeader; this keeps the progress bar and the "why the share is tiny"
 *  note, which explains an intentional design decision and must stay. */
function GoalsProgress({
  overall,
  allTracking,
  offTrack,
}: {
  overall: number;
  allTracking: boolean;
  offTrack: string[];
}) {
  return (
    <div className="rounded-xl border border-border bg-gradient-to-br from-primary/[0.07] to-card p-5 shadow-sm">
      <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
        <span>Saved of total target</span>
        <span className="tabular-nums">{sharePct(overall)}</span>
      </div>
      <Progress value={overall} />
      {/* The saved share is tiny early on by design — the SIP carries these,
          not the starting balance. Said plainly so the bar doesn't read as
          failure next to a 99% probability on the cards below. */}
      <p className="mt-2 text-2xs leading-relaxed text-muted-foreground">
        {allTracking ? (
          <>Small share is normal this early — the SIP does the work; judge these on the odds below.</>
        ) : (
          <>
            Small share is normal this early — the SIP does the work; judge these on the odds
            below.{" "}
            <span className="font-medium text-foreground">
              {offTrack.join(" and ")} under {ON_TRACK * 100}%
            </span>
            .
          </>
        )}{" "}
        FI is paused until 2030 (its old share now goes to the Emergency Fund) — it lives on{" "}
        <a href="#retirement" className="font-medium text-foreground underline underline-offset-2">
          Retirement
        </a>
        .
      </p>
    </div>
  );
}

function GoalCard({
  analysis,
  goal,
  mfOptions,
  onChanged,
  freshSim,
  onBaselineSim,
}: {
  analysis: GoalAnalysis;
  goal: Goal | undefined;
  mfOptions: MfOption[];
  onChanged: () => void;
  freshSim: GoalSimulation | null;
  onBaselineSim: (sim: GoalSimulation) => void;
}) {
  const [contribution, setContribution] = useState(goal?.monthly_contribution ?? 0);
  const [target, setTarget] = useState(goal?.target_value ?? 0);
  const [targetDate, setTargetDate] = useState(goal?.target_date ?? "");
  const [isins, setIsins] = useState<string[]>(goal?.assigned_isins ?? []);
  const [buckets, setBuckets] = useState<string[]>(goal?.assigned_buckets ?? []);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [solving, setSolving] = useState(false);
  const [solved, setSolved] = useState<RequiredContribution | null>(null);
  const [stressing, setStressing] = useState(false);
  const [stress, setStress] = useState<StressTest | null>(null);

  const [showWhatIf, setShowWhatIf] = useState(false);

  // The analysis endpoint serves the cached `goal_simulation` row, which goes
  // stale the moment a goal changes. Re-run the goal at its own saved values
  // and report up, so cards and the summary's on-track count agree. This lives
  // on the card rather than inside WhatIfSliders because that panel is now
  // collapsed by default — the correctness fix must not depend on a disclosure
  // the user may never open.
  // Held in a ref: the parent passes an inline arrow, so listing it as a
  // dependency would re-arm this effect every render and re-simulate forever.
  const onBaselineRef = React.useRef(onBaselineSim);
  onBaselineRef.current = onBaselineSim;

  React.useEffect(() => {
    if (!goal?.target_value || !goal?.target_date) return;
    let cancelled = false;
    void (async () => {
      try {
        const fresh = await api.simulateGoal(goal.id, {
          monthly_contribution: goal.monthly_contribution,
          target_value: goal.target_value ?? 0,
        });
        if (!cancelled) onBaselineRef.current(fresh);
      } catch {
        /* keep the cached figure */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [goal?.id, goal?.monthly_contribution, goal?.target_value, goal?.target_date]);

  const sim = freshSim ?? analysis.simulation;
  const saved = analysis.assigned_value;
  const fundedPct = target ? Math.min(100, (saved / target) * 100) : 0;
  const gap = sim && target ? target - sim.median_ending_value : null;
  // Goal targets are stated in nominal rupees at their target date, so
  // deflating shows what that will actually buy. (Retirement runs the opposite
  // conversion — see lib/inflation.ts.)
  const targetToday = target ? inTodaysMoney(target, targetDate || null) : null;

  const toggle = (list: string[], setList: (v: string[]) => void, key: string) =>
    setList(list.includes(key) ? list.filter((x) => x !== key) : [...list, key]);

  async function recalc() {
    if (!goal) return;
    setBusy(true);
    try {
      await api.updateGoal(goal.id, {
        monthly_contribution: contribution,
        target_value: target,
        target_date: targetDate || null,
        assigned_isins: isins,
        assigned_buckets: buckets,
      });
      await api.simulateGoal(goal.id, {
        monthly_contribution: contribution,
        target_value: target,
      });
      setSolved(null);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function solve() {
    if (!goal) return;
    setSolving(true);
    try {
      setSolved(await api.requiredContribution(goal.id, ON_TRACK));
    } finally {
      setSolving(false);
    }
  }

  async function runStress() {
    if (!goal) return;
    if (stress) {
      setStress(null);
      return;
    }
    setStressing(true);
    try {
      setStress(await api.stressTest(goal.id));
    } finally {
      setStressing(false);
    }
  }

  return (
    <div className="flex flex-col rounded-xl border border-border bg-card p-5 shadow-sm transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-md motion-reduce:transform-none motion-reduce:transition-none">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Target className="size-[18px]" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="flex items-center gap-1.5 font-semibold leading-tight">
              {analysis.name}
              <AskAI
                tip="AI stress test"
                question={`Simulate the ${analysis.name} goal with a 30% market crash at the start — does it still succeed? Then compare with the base case.`}
              />
            </h3>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
              <CalendarClock className="size-3" />
              {analysis.months_remaining != null
                ? `${analysis.months_remaining} mo left`
                : "Open-ended"}
              {targetDate ? ` · by ${dateOnly(targetDate)}` : ""}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          {analysis.violations.map((v) => (
            <Badge key={v.code} variant={severityVariant(v.severity)}>
              {v.title}
            </Badge>
          ))}
          <Button
            variant={editing ? "secondary" : "ghost"}
            size="icon-sm"
            onClick={() => setEditing((e) => !e)}
            aria-label="Goal settings"
          >
            <Settings2 />
          </Button>
        </div>
      </div>

      {/* Saved of target + funded % */}
      <div className="mt-4">
        <div className="flex items-end justify-between">
          <div>
            <span className="text-2xl font-semibold tabular-nums">{inr(saved)}</span>
            <span className="ml-1.5 text-sm text-muted-foreground">of {inr(target)}</span>
          </div>
          <div className="text-right">
            <div className="text-lg font-semibold tabular-nums text-primary">
              {sharePct(fundedPct)}
            </div>
            <div className="text-xs text-muted-foreground">saved</div>
          </div>
        </div>
        <Progress value={fundedPct} className="mt-2" />
        {targetToday != null ? (
          <p className="mt-1.5 text-2xs tabular-nums text-muted-foreground">
            {inr(target)} at that date buys about{" "}
            <span className="font-medium text-foreground">{inr(targetToday)}</span> of today&apos;s
            purchasing power (at {PLANNING_INFLATION * 100}% inflation).
          </p>
        ) : null}
      </div>

      {/* Settings (collapsible) */}
      {editing ? (
        <div className="mt-4 space-y-3 rounded-lg border border-border bg-muted/30 p-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Target value</label>
              <div className="mt-1 flex items-center gap-1.5">
                <span className="text-sm text-muted-foreground">₹</span>
                <Input
                  type="number"
                  min={0}
                  value={target}
                  onChange={(e) => setTarget(Number(e.target.value))}
                  className="tabular-nums"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Deadline</label>
              <Input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Monthly contribution
              </label>
              <div className="mt-1 flex items-center gap-1.5">
                <span className="text-sm text-muted-foreground">₹</span>
                <Input
                  type="number"
                  min={0}
                  value={contribution}
                  onChange={(e) => setContribution(Number(e.target.value))}
                  className="tabular-nums"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground">
              Buckets this goal draws from
            </label>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {BUCKET_OPTIONS.map((key) => (
                <button
                  key={key}
                  onClick={() => toggle(buckets, setBuckets, key)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                    buckets.includes(key)
                      ? "border-transparent bg-primary text-primary-foreground"
                      : "border-border hover:bg-muted",
                  )}
                >
                  {BUCKETS[key].label}
                </button>
              ))}
            </div>
          </div>

          {mfOptions.length > 0 ? (
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Funds this goal draws from
              </label>
              <div className="mt-1 max-h-40 space-y-1 overflow-y-auto">
                {mfOptions.map((o) => (
                  <label key={o.isin} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={isins.includes(o.isin)}
                      onChange={() => toggle(isins, setIsins, o.isin)}
                      className="accent-[var(--primary)]"
                    />
                    <span className="truncate">{o.name}</span>
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex justify-end">
            <Button onClick={recalc} disabled={busy || !goal} size="sm">
              <RefreshCw className={busy ? "animate-spin" : ""} />
              Save &amp; Recalculate
            </Button>
          </div>
        </div>
      ) : null}

      {/* Monte Carlo projection */}
      <div className="mt-4 flex-1 rounded-lg border border-border bg-muted/30 p-4">
        {sim ? (
          <>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                Probability of hitting target by deadline
              </span>
              <span
                className={cn(
                  "text-2xl font-semibold tabular-nums",
                  probabilityColor(sim.probability_of_success),
                )}
              >
                {(sim.probability_of_success * 100).toFixed(0)}%
              </span>
            </div>
            <div className="mt-3">
              <SimRangeBar
                p10={sim.p10_value}
                p90={sim.p90_value}
                median={sim.median_ending_value}
                target={target || sim.median_ending_value}
              />
            </div>
            {gap != null ? (
              <p className="mt-3 text-xs text-muted-foreground">
                {gap > 0 ? (
                  <>
                    Median projection is{" "}
                    <span className="font-medium text-loss">{inr(gap)} short</span> of
                    target.
                  </>
                ) : (
                  <>
                    Median projection{" "}
                    <span className="font-medium text-gain">
                      exceeds target by {inr(-gap)}
                    </span>
                    .
                  </>
                )}
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            No simulation yet — open settings, set a target, and Recalculate.
          </p>
        )}
      </div>

      {/* Solver */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button onClick={solve} disabled={solving || !goal} variant="outline" size="sm">
          <Wand2 className={solving ? "animate-spin" : ""} />
          Required SIP
        </Button>
        <Button
          onClick={runStress}
          disabled={stressing || !goal}
          variant={stress ? "secondary" : "outline"}
          size="sm"
        >
          <ShieldAlert className={stressing ? "animate-spin" : ""} />
          Stress test
        </Button>
        <Button
          onClick={() => setShowWhatIf((v) => !v)}
          disabled={!goal}
          variant={showWhatIf ? "secondary" : "outline"}
          size="sm"
        >
          <SlidersHorizontal />
          What if…
        </Button>
        {solved ? (
          solved.reachable ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">
                ~
                <span className="font-semibold text-foreground">
                  {inr(solved.required_monthly_contribution)}/mo
                </span>
              </span>
              <Button
                size="xs"
                variant="secondary"
                onClick={() => {
                  setContribution(solved.required_monthly_contribution);
                  setEditing(true);
                }}
              >
                Apply
              </Button>
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">
              Even {inr(solved.required_monthly_contribution)}/mo only reaches{" "}
              {(solved.probability_of_success * 100).toFixed(0)}% — consider a longer
              horizon or lower target.
            </span>
          )
        ) : null}
      </div>

      {/* Stress test ladder */}
      {stress ? (
        <div className="mt-3 rounded-lg border border-border bg-muted/30 p-4">
          <div className="mb-2 text-xs font-medium text-muted-foreground">
            If markets fall today — probability of still hitting target
          </div>
          <div className="space-y-1.5">
            {stress.scenarios.map((s) => {
              const drop = stress.baseline_probability - s.probability_of_success;
              return (
                <div key={s.label} className="flex items-center gap-2">
                  <span className="w-40 shrink-0 text-xs">{s.label}</span>
                  <div className="h-2 flex-1 rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-2 rounded-full",
                        s.probability_of_success >= 0.75
                          ? "bg-gain"
                          : s.probability_of_success >= 0.5
                            ? "bg-warning"
                            : "bg-loss",
                      )}
                      style={{ width: `${Math.max(2, s.probability_of_success * 100)}%` }}
                    />
                  </div>
                  <span
                    className={cn(
                      "w-10 shrink-0 text-right text-xs font-semibold tabular-nums",
                      probabilityColor(s.probability_of_success),
                    )}
                  >
                    {(s.probability_of_success * 100).toFixed(0)}%
                  </span>
                  <span className="w-14 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                    {s.shock === 0 ? "—" : `−${(drop * 100).toFixed(0)}pt`}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            A one-time crash at t=0, scaled by each sleeve&apos;s volatility — liquid
            sleeves barely move, equity takes the full hit. Resilient goals hold their
            probability across the ladder.
          </p>
        </div>
      ) : null}
      {goal && showWhatIf ? <WhatIfSliders goal={goal} /> : null}
    </div>
  );
}

export function GoalsTab() {
  const analyses = useApi<GoalAnalysis[]>(() => api.goalsAnalysis(), []);
  // Each card's WhatIfSliders re-runs its goal at the saved values on mount;
  // collecting those here keeps the summary's on-track count and the cards
  // reading the same numbers instead of the summary trusting a stale cache.
  const [freshSims, setFreshSims] = useState<Map<string, GoalSimulation>>(new Map());
  const noteSim = useCallback(
    (key: string, sim: GoalSimulation) =>
      setFreshSims((prev) => {
        const cur = prev.get(key);
        if (cur && cur.run_ts === sim.run_ts) return prev; // no-op, avoid re-render loop
        return new Map(prev).set(key, sim);
      }),
    [],
  );
  const goals = useApi<Goal[]>(() => api.goals(), []);
  const snap = useApi<Snapshot>(() => api.latestSnapshot(), []);

  if (analyses.loading || goals.loading) {
    // Mirrors the tab's shape (header, progress band, two-up goal cards),
    // rounded-xl to match the cards it becomes — no reflow on swap.
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-80 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      </div>
    );
  }

  if (analyses.error || !analyses.data) {
    return (
      <div className="px-4 py-8 text-center">
        <p className="mx-auto max-w-sm text-sm text-muted-foreground">
          Goal analysis needs a snapshot — refresh the portfolio first.
        </p>
      </div>
    );
  }

  // FI is funded and simulated like any other goal — it just isn't a card here
  // (see HIDDEN_GOAL_KEYS); the Retirement tab owns it.
  const visible = analyses.data.filter((a) => !HIDDEN_GOAL_KEYS.has(a.key));
  const goalByKey = new Map((goals.data ?? []).map((g) => [g.key, g]));
  const mfOptions: MfOption[] = (snap.data?.holdings ?? [])
    .filter((h) => h.type === "mf")
    .map((h) => ({ isin: h.symbol, name: h.name ?? h.symbol }));

  const reload = () => {
    void analyses.reload();
    void goals.reload();
  };

  const totals = goalTotals(visible, goalByKey, freshSims);
  const monthlySip = (goals.data ?? []).reduce((sum, g) => sum + g.monthly_contribution, 0);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Target}
        title="Goals"
        subtitle="Travel, Vehicle and Emergency — funded by monthly SIP and judged on the odds, not the balance."
        stats={[
          { label: "Total target", value: inr(totals.totalTarget) },
          { label: "Saved so far", value: inr(totals.totalSaved), tone: "primary" },
          { label: "Monthly SIP", value: `${inr(monthlySip)}/mo`, tone: "primary" },
          {
            label: "On track",
            value: `${totals.onTrack} of ${totals.count}`,
            tone: totals.allTracking ? "gain" : "warning",
          },
        ]}
      />
      <Phase0Card />
      <GoalsProgress
        overall={totals.overall}
        allTracking={totals.allTracking}
        offTrack={totals.offTrack}
      />
      {/* Sits directly under the "judge these on the odds" note, because it is
          the caveat to exactly that claim. Renders nothing when contributions
          are tracking the plan. */}
      <ContributionRealityBand />
      <JointOptimizePanel planned={monthlySip} />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {visible.map((a) => (
          <GoalCard
            key={a.key}
            analysis={a}
            goal={goalByKey.get(a.key)}
            mfOptions={mfOptions}
            onChanged={reload}
            freshSim={freshSims.get(a.key) ?? null}
            onBaselineSim={(sim) => noteSim(a.key, sim)}
          />
        ))}
      </div>
    </div>
  );
}
