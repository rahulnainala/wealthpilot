"use client";

import { useEffect, useState } from "react";
import { PiggyBank } from "lucide-react";

import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { RetirementGlideChart } from "@/components/charts/RetirementGlideChart";
import { IncomeTab } from "@/components/tabs/IncomeTab";
import { useApi } from "@/hooks/useApi";
import { SELL_THRESHOLD_PCT, WINDOW_END_LABEL } from "@/lib/exitPlan";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import { cn } from "@/lib/utils";

const FI_GOAL_KEY = "fi";
const TRAVEL_GOAL_KEY = "travel";
const VEHICLE_GOAL_KEY = "vehicle";
// Fallback if the FI goal isn't loaded yet — mirrors its current values
// (Financial Independence, target 2045-01-01, ₹2Cr placeholder). Monthly is
// 0: FI is paused until 2030 — the Emergency Fund absorbed
// its old share. The step-up toggle below is what makes FI's SIP
// real again, starting from this ₹0 base.
const FALLBACK_YEARS = 14;
const FALLBACK_TARGET = 15_000_000;
const FALLBACK_MONTHLY = 0;
// Owner's planning floor (2026-07-20) — the API clamps below this too.
const MIN_INFLATION = 6;
// How long the corpus needs to survive drawdown, once retired. Confirmed
// with the owner (2026-07-20) as the default starting point for the slider.
const DEFAULT_RETIREMENT_YEARS = 25;

function yearsUntil(dateStr: string): number {
  const ms = new Date(dateStr).getTime() - Date.now();
  return Math.max(1, Math.round(ms / (365.25 * 24 * 3600 * 1000)));
}

function monthsUntil(dateStr: string): number {
  const ms = new Date(dateStr).getTime() - Date.now();
  return Math.max(1, Math.round(ms / (30.44 * 24 * 3600 * 1000)));
}

type Fi = NonNullable<Awaited<ReturnType<typeof api.aiFi>>>;
type FiPlan = NonNullable<Awaited<ReturnType<typeof api.aiFiPlan>>>;

/** A labelled range slider with its live value shown inline. */
function Field({
  label,
  hint,
  value,
  onChange,
  min,
  max,
  step,
  format,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (n: number) => void;
  min: number;
  max: number;
  step: number;
  format: (n: number) => string;
}) {
  return (
    <label className="block text-sm">
      <span className="flex items-baseline justify-between gap-3 tabular-nums">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{format(value)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full accent-[var(--primary)]"
        aria-label={label}
        aria-valuetext={format(value)}
      />
      {hint ? <span className="mt-0.5 block text-2xs text-muted-foreground">{hint}</span> : null}
    </label>
  );
}

/** One figure shown in both future rupees and today's purchasing power. */
function DualRow({
  label,
  nominal,
  today,
  strong,
}: {
  label: string;
  nominal: string;
  today: string;
  strong?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-[1fr_auto_auto] items-baseline gap-x-4 py-1.5 text-sm tabular-nums",
        strong && "border-t border-border pt-2",
      )}
    >
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("text-right", strong ? "font-medium" : "text-muted-foreground")}>
        {nominal}
      </span>
      <span
        className={cn(
          "min-w-[7.5rem] text-right",
          strong ? "font-semibold text-gain" : "font-medium",
        )}
      >
        {today}
      </span>
    </div>
  );
}

/**
 * Phase 31: whole-portfolio FI projection + safe-withdrawal income.
 *
 * Opens on the real Financial Independence goal (Goals tab, key "fi") rather
 * than generic numbers, models inflation at a 6% floor (the target slider is
 * read as today's purchasing power), and can project the post-sell-off
 * allocation — the legacy dividend basket sold and reinvested as equity per
 * the +10%/WINDOW_END_LABEL exit plan.
 */
export function RetirementTab() {
  const goals = useApi(() => api.goals(), []);
  const fiGoal = goals.data?.find((g) => g.key === FI_GOAL_KEY) ?? null;
  const travelGoal = goals.data?.find((g) => g.key === TRAVEL_GOAL_KEY) ?? null;
  const vehicleGoal = goals.data?.find((g) => g.key === VEHICLE_GOAL_KEY) ?? null;
  const travelMonths = travelGoal?.target_date ? monthsUntil(travelGoal.target_date) : undefined;
  const vehicleMonths = vehicleGoal?.target_date
    ? monthsUntil(vehicleGoal.target_date)
    : undefined;

  const [years, setYears] = useState(FALLBACK_YEARS);
  const [target, setTarget] = useState(FALLBACK_TARGET);
  const [monthly, setMonthly] = useState(FALLBACK_MONTHLY);
  const [swr, setSwr] = useState(3.5);
  const [inflation, setInflation] = useState(MIN_INFLATION);
  const [postSelloff, setPostSelloff] = useState(true);
  const [retirementYears, setRetirementYears] = useState(DEFAULT_RETIREMENT_YEARS);
  const [stepUp, setStepUp] = useState(true);
  const [res, setRes] = useState<Fi | null>(null);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<FiPlan | null>(null);
  const [planBusy, setPlanBusy] = useState(false);
  const [primed, setPrimed] = useState(false);

  // Prime the sliders from the real FI goal once it loads (one-shot — after
  // that the user's own drags win, so this never fights their input).
  useEffect(() => {
    if (primed || !fiGoal) return;
    if (fiGoal.target_value) setTarget(fiGoal.target_value);
    if (fiGoal.monthly_contribution) setMonthly(fiGoal.monthly_contribution);
    if (fiGoal.target_date) setYears(yearsUntil(fiGoal.target_date));
    setPrimed(true);
  }, [fiGoal, primed]);

  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const fresh = await api.aiFi({
          years,
          target,
          monthly,
          swr: swr / 100,
          inflation: inflation / 100,
          postSelloff,
        });
        if (!cancelled) setRes(fresh);
      } catch {
        /* keep last */
      } finally {
        if (!cancelled) setBusy(false);
      }
    }, 450);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [years, target, monthly, swr, inflation, postSelloff]);

  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(async () => {
      setPlanBusy(true);
      try {
        const fresh = await api.aiFiPlan({
          years,
          target,
          monthly,
          swr: swr / 100,
          inflation: inflation / 100,
          postSelloff,
          retirementYears,
          stepUp,
          travelMonths,
          vehicleMonths,
        });
        if (!cancelled) setPlan(fresh);
      } catch {
        /* keep last */
      } finally {
        if (!cancelled) setPlanBusy(false);
      }
    }, 450);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [
    years,
    target,
    monthly,
    swr,
    inflation,
    postSelloff,
    retirementYears,
    stepUp,
    travelMonths,
    vehicleMonths,
  ]);

  const prob = res ? Math.round(res.probability_of_success * 100) : null;
  const tone =
    prob == null ? "text-muted-foreground" : prob >= 75 ? "text-gain" : prob >= 40 ? "text-warning" : "text-loss";
  const offPlan =
    fiGoal != null &&
    (target !== fiGoal.target_value || monthly !== fiGoal.monthly_contribution);
  const shortfall = res ? res.required_monthly_contribution - res.monthly_contribution : 0;

  const resetToPlan = () => {
    if (!fiGoal) return;
    if (fiGoal.target_value) setTarget(fiGoal.target_value);
    setMonthly(fiGoal.monthly_contribution);
    if (fiGoal.target_date) setYears(yearsUntil(fiGoal.target_date));
  };

  return (
    <div className="space-y-4">
      <PageHeader
        icon={PiggyBank}
        title="Retirement"
        subtitle="Whole-portfolio FI projection and safe-withdrawal income — drag the sliders to explore."
        stats={[
          { label: "Horizon", value: `${years}y` },
          {
            label: "Monthly SIP",
            value: monthly > 0 ? `${inr(monthly)}/mo` : "Paused",
            tone: monthly > 0 ? "primary" : "default",
          },
        ]}
      />

      {/* Verdict strip — the one-line answer before any detail. */}
      {res ? (
        <div
          className={cn(
            "flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-xl border px-5 py-3.5",
            prob != null && prob >= 75
              ? "border-gain/40 bg-gain/[0.06]"
              : prob != null && prob >= 40
                ? "border-warning/40 bg-warning/[0.07]"
                : "border-loss/40 bg-loss/[0.07]",
          )}
        >
          <div className="flex items-baseline gap-3">
            <span className={cn("text-3xl font-semibold tabular-nums", tone)}>
              {busy ? "…" : `${prob}%`}
            </span>
            <span className="text-sm text-muted-foreground">
              odds of reaching {inr(res.target_today)} (today&apos;s money) in {res.years}y
            </span>
          </div>
          <p className="text-sm tabular-nums">
            <span className="text-muted-foreground">Buys you </span>
            <span className="font-semibold text-gain">
              {inr(res.sustainable_monthly_income_today)}/mo
            </span>
            <span className="text-muted-foreground"> in today&apos;s purchasing power</span>
          </p>
        </div>
      ) : null}

      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Panel
          title="Your plan"
          description="Whole-portfolio Monte Carlo to a corpus — drag to explore."
        >
          <div className="space-y-4">
            <Field
              label="Years to retirement"
              value={years}
              onChange={setYears}
              min={1}
              max={40}
              step={1}
              format={(n) => `${n}y`}
            />
            <Field
              label="Target corpus"
              hint="In today's money — inflated below to what you'd actually need."
              value={target}
              onChange={setTarget}
              min={5_000_000}
              max={100_000_000}
              step={1_000_000}
              format={inr}
            />
            <Field
              label="Monthly investment"
              value={monthly}
              onChange={setMonthly}
              min={0}
              max={200_000}
              step={1_000}
              format={(n) => `${inr(n)}/mo`}
            />
            <Field
              label="Inflation"
              hint="Floored at 6% — long-run Indian CPI; healthcare and education run hotter."
              value={inflation}
              onChange={setInflation}
              min={MIN_INFLATION}
              max={10}
              step={0.5}
              format={(n) => `${n.toFixed(1)}%`}
            />
            <Field
              label="Withdrawal rate"
              value={swr}
              onChange={setSwr}
              min={2.5}
              max={6}
              step={0.1}
              format={(n) => `${n.toFixed(1)}%`}
            />
            <Field
              label="Years in retirement"
              hint="How long the corpus needs to last after you stop working."
              value={retirementYears}
              onChange={setRetirementYears}
              min={10}
              max={40}
              step={1}
              format={(n) => `${n}y`}
            />
          </div>

          <button
            type="button"
            aria-pressed={stepUp}
            onClick={() => setStepUp((v) => !v)}
            className={cn(
              "mt-4 flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors",
              stepUp
                ? "border-primary/50 bg-primary/[0.07]"
                : "border-border hover:bg-muted/50",
            )}
          >
            <span
              className={cn(
                "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border text-[10px] font-bold",
                stepUp
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-input text-transparent",
              )}
              aria-hidden="true"
            >
              ✓
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-medium">SIP step-up</span>
              <span className="block text-2xs text-muted-foreground">
                Models Travel (2030) and Vehicle (2031) completing and rolling their freed SIP
                (₹10k, then ₹6k) into FI, instead of ₹0/mo until then — FI is paused for now,
                the Emergency Fund has its old share.
              </span>
            </span>
          </button>

          <button
            type="button"
            aria-pressed={postSelloff}
            onClick={() => setPostSelloff((v) => !v)}
            className={cn(
              "mt-4 flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors",
              postSelloff
                ? "border-primary/50 bg-primary/[0.07]"
                : "border-border hover:bg-muted/50",
            )}
          >
            <span
              className={cn(
                "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border text-[10px] font-bold",
                postSelloff
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-input text-transparent",
              )}
              aria-hidden="true"
            >
              ✓
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-medium">After the sell-off</span>
              <span className="block text-2xs text-muted-foreground">
                Models the legacy dividend basket already sold and reinvested as equity per the
                +{SELL_THRESHOLD_PCT}% / {WINDOW_END_LABEL} exit plan
                {res ? ` — ${res.equity_pct.toFixed(0)}% equity` : ""}. Higher expected return,
                higher volatility.
              </span>
            </span>
          </button>

          <div className="mt-3 flex items-start justify-between gap-3 rounded-lg border border-border bg-card/50 p-3 text-2xs text-muted-foreground">
            <p>
              Opens on your <span className="font-medium text-foreground">Financial Independence</span>{" "}
              goal (2045, ₹2Cr placeholder). Paused until 2030 — ₹0/mo for now, the Emergency Fund has its old
              SIP share; the step-up above models it resuming.
            </p>
            {offPlan ? (
              <button
                type="button"
                onClick={resetToPlan}
                className="shrink-0 whitespace-nowrap rounded-md border border-input px-2 py-1 font-medium text-foreground hover:bg-muted"
              >
                Reset to plan
              </button>
            ) : null}
          </div>
        </Panel>

        <Panel title="Projection" description="Engine-cited estimate, not a guarantee.">
          {!res ? (
            // res only stays null during the very first simulation (later runs
            // keep the last result), so the empty state is always "loading",
            // never "waiting for you" — the sliders are already set.
            <div className="px-4 py-8 text-center">
              <p className="mx-auto max-w-sm text-sm text-muted-foreground">Simulating…</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-[1fr_auto_auto] gap-x-4 border-b border-border pb-1.5 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                <span />
                <span className="text-right">In {new Date().getFullYear() + res.years}</span>
                <span className="min-w-[7.5rem] text-right">Today&apos;s money</span>
              </div>

              <div>
                <DualRow
                  label="Target corpus"
                  nominal={inr(res.target_nominal)}
                  today={inr(res.target_today)}
                />
                <DualRow
                  label="Median outcome"
                  nominal={inr(res.median_corpus)}
                  today={inr(res.median_corpus_today)}
                />
                <DualRow
                  label="Pessimistic (p10)"
                  nominal={inr(res.p10_corpus)}
                  today={inr(res.p10_corpus_today)}
                />
                <DualRow
                  label="Optimistic (p90)"
                  nominal={inr(res.p90_corpus)}
                  today={inr(res.p90_corpus_today)}
                />
                <DualRow
                  strong
                  label={`Safe income @ ${swr.toFixed(1)}%`}
                  nominal={`${inr(res.sustainable_monthly_income)}/mo`}
                  today={`${inr(res.sustainable_monthly_income_today)}/mo`}
                />
              </div>

              <p className="text-2xs leading-relaxed text-muted-foreground">
                At {res.inflation * 100}% inflation, {inr(res.target_today)} of today&apos;s
                purchasing power means accumulating {inr(res.target_nominal)} by then — that gap is
                the whole reason the right-hand column exists. A {swr.toFixed(1)}% withdrawal rate on
                the median corpus; sequence-of-returns risk means real outcomes vary, so de-risk near
                the date.
              </p>
            </div>
          )}
        </Panel>
      </div>

      {/* The whole journey, not just the two snapshots above — accumulation
          into drawdown, on one continuous simulated path. */}
      <Panel
        title="Glide path"
        description={`Accumulation through ${retirementYears}y of drawdown, one continuous path.`}
      >
        {!plan ? (
          <div className="px-4 py-8 text-center">
            <p className="mx-auto max-w-sm text-sm text-muted-foreground">Simulating…</p>
          </div>
        ) : plan.bands.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="mx-auto max-w-sm text-sm text-muted-foreground">
              Not enough data to simulate a path.
            </p>
          </div>
        ) : (
          <RetirementGlideChart bands={plan.bands} retirementMonth={plan.years * 12} />
        )}
      </Panel>

      {/* Answers what the point-estimate above can't: does the corpus outlive
          the drawdown, and roughly when does it run dry if not. */}
      {plan ? (
        <div
          className={cn(
            "flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-xl border px-5 py-3.5",
            plan.depletion_probability <= 0.1
              ? "border-gain/40 bg-gain/[0.06]"
              : plan.depletion_probability <= 0.4
                ? "border-warning/40 bg-warning/[0.07]"
                : "border-loss/40 bg-loss/[0.07]",
          )}
        >
          <div className="flex items-baseline gap-3">
            <span
              className={cn(
                "text-3xl font-semibold tabular-nums",
                plan.depletion_probability <= 0.1
                  ? "text-gain"
                  : plan.depletion_probability <= 0.4
                    ? "text-warning"
                    : "text-loss",
              )}
            >
              {planBusy ? "…" : `${Math.round(plan.depletion_probability * 100)}%`}
            </span>
            <span className="text-sm text-muted-foreground">
              odds the corpus runs dry before {retirementYears}y of drawdown ends
              {plan.median_depletion_year ? (
                <>
                  {" "}
                  — median <span className="font-medium text-foreground">{plan.median_depletion_year}</span>
                </>
              ) : null}
            </span>
          </div>
          {plan.depletion_probability < 1 ? (
            <p className="text-sm tabular-nums">
              <span className="text-muted-foreground">Median leftover at the end: </span>
              <span className="font-semibold text-gain">
                {inr(plan.median_terminal_value_today)}
              </span>
              <span className="text-muted-foreground"> in today&apos;s money</span>
            </p>
          ) : null}
        </div>
      ) : null}

      {/* The actionable number: what it would actually take. */}
      {res ? (
        <Panel
          title="Reality check"
          description={`What it takes to reach ${Math.round(res.target_probability * 100)}% odds.`}
        >
          <p className="mb-3 text-2xs leading-relaxed text-muted-foreground">
            This baseline assumes a flat {inr(res.monthly_contribution)}/mo forever — the Glide
            path above shows the fuller picture with SIP step-up as Travel/Vehicle complete.
          </p>
          {shortfall <= 0 ? (
            <p className="text-sm">
              <span className="font-semibold text-gain">On track.</span>{" "}
              <span className="text-muted-foreground">
                {inr(res.monthly_contribution)}/mo already clears{" "}
                {Math.round(res.target_probability * 100)}% odds for this target.
              </span>
            </p>
          ) : !res.required_reachable ? (
            <p className="text-sm">
              <span className="font-semibold text-loss">Out of reach by SIP alone.</span>{" "}
              <span className="text-muted-foreground">
                Even {inr(res.required_monthly_contribution)}/mo wouldn&apos;t get there in{" "}
                {res.years} years. Worth revisiting the target, the date, or both — the Goals tab is
                where those live.
              </span>
            </p>
          ) : (
            <div className="space-y-2.5">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="text-2xl font-semibold tabular-nums text-warning">
                  {inr(res.required_monthly_contribution)}/mo
                </span>
                <span className="text-sm text-muted-foreground">
                  needed vs {inr(res.monthly_contribution)}/mo today — a gap of{" "}
                  <span className="font-medium text-foreground">{inr(shortfall)}/mo</span>
                </span>
              </div>
              <p className="text-2xs leading-relaxed text-muted-foreground">
                FI is the long game and deliberately paused right now — Travel (2030) and Vehicle
                (2031) run first, with the Emergency Fund holding FI&apos;s old share in the meantime. This
                baseline is flat-₹0/mo on purpose; the Glide path above shows the real picture once
                Travel&apos;s SIP rolls into FI in 2030. Worth watching, not worth panicking over.
              </p>
            </div>
          )}
        </Panel>
      ) : null}

      <IncomeTab />
    </div>
  );
}
