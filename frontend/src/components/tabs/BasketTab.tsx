"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, PieChart } from "lucide-react";

import { Loadable } from "@/components/Loadable";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import {
  EXIT_STATUS_META,
  SELL_THRESHOLD_PCT,
  WINDOW_END_LABEL,
  buildExitItem,
  isSellNow,
  monthsLeftLabel,
  sortExitItems,
  type ExitItem,
} from "@/lib/exitPlan";
import { inr, pct, signColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Basket, BasketMode, BasketSleeve, Snapshot } from "@/lib/types";

const SPLIT_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#14b8a6"];

// FI is paused — no new SIP until Travel completes in 2030 and frees its
// share. Kept out of the active "3 baskets"
// grouping below so it reads as paused, not as a fourth equal basket, while
// its held ELSS/gold positions still show up honestly.
const PAUSED_GOAL_KEYS = new Set(["fi"]);

const MODE_META: Record<BasketMode, { label: string; className: string }> = {
  core: { label: "Continue SIP", className: "bg-primary/15 text-primary" },
  planned: { label: "Set up SIP", className: "bg-gain/15 text-gain" },
  hold: { label: "Hold", className: "bg-muted text-muted-foreground" },
  bonus: { label: "Bonus-funded", className: "bg-warning/15 text-warning" },
};

function sipLabel(mode: BasketMode, monthly: number, pct: number): string {
  if (mode === "bonus") return "from bonuses";
  if (mode === "hold") return "no new money";
  return `${inr(monthly)}/mo · ${pct}%`;
}

/**
 * The sleeve header's money summary. A zero monthly_contribution isn't
 * always the same story — near-cash can be bonus-only, FI is paused
 * pending 2030 — so this reads it off the actual position modes
 * rather than assuming from the number alone.
 */
function sleeveMoneyLabel(sleeve: BasketSleeve, scale: number): string {
  if (sleeve.monthly_contribution > 0) return `${inr(sleeve.monthly_contribution * scale)}/mo`;
  if (sleeve.positions.every((p) => p.mode === "hold")) return "paused — no new money";
  if (sleeve.positions.some((p) => p.mode === "bonus")) return "bonus-funded";
  return "no new money";
}

/** Budget the SIP routing can be explored across (₹10k–₹2L). The floor
 *  stays at ₹10k so the ₹20k plan sits on the
 *  scale and "Reset" always has somewhere to land. */
const BUDGET_MIN = 10_000;
const BUDGET_MAX = 200_000;
const BUDGET_STEP = 1_000;

function MonthlySplitBar({ basket, budget }: { basket: Basket; budget: number }) {
  if (basket.monthly_split.length === 0) return null;
  // Percentages are the plan's shares (50/30/20); only the rupee amounts scale
  // with the chosen budget, so the routing ratio is never silently altered.
  const scale = basket.monthly_total > 0 ? budget / basket.monthly_total : 0;
  return (
    <div>
      <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
        <span>Monthly SIP routing</span>
        <span className="tabular-nums">{inr(budget)}/mo</span>
      </div>
      <div className="flex h-3 overflow-hidden rounded-full">
        {basket.monthly_split.map((s, i) => (
          <div
            key={s.goal_name}
            style={{ width: `${s.pct}%`, background: SPLIT_COLORS[i % SPLIT_COLORS.length] }}
            title={`${s.goal_name}: ${inr(s.monthly * scale)}/mo (${s.pct}%)`}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {basket.monthly_split.map((s, i) => (
          <span key={s.goal_name} className="flex items-center gap-1.5">
            <span
              className="size-2 rounded-full"
              style={{ background: SPLIT_COLORS[i % SPLIT_COLORS.length] }}
            />
            {s.goal_name}
            <span className="text-muted-foreground tabular-nums">
              {inr(s.monthly * scale)} · {s.pct}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * Monthly-budget control for the routing preview.
 *
 * The stored plan is ₹20k split 50/30/20. This lets the owner see where a
 * different monthly amount would land without editing every goal — it scales
 * rupee amounts only, never the shares. Deliberately **preview-only**: goal
 * contributions (and every simulation that reads them) stay untouched until
 * they're changed on the Goals tab, so exploring here can't quietly re-rate
 * Travel or Vehicle.
 */
function BudgetControl({
  budget,
  setBudget,
  planned,
  basket,
  scale,
}: {
  budget: number;
  setBudget: (n: number) => void;
  planned: number;
  basket: Basket;
  scale: number;
}) {
  const delta = budget - planned;

  // The number field keeps its own draft text so it can be typed into freely.
  // The old field was `value={budget}` and clamped on *every* keystroke, so
  // typing "2" snapped to ₹10k and the next digits piled onto that — a typed
  // budget never matched what you entered, and the funds below scaled to the
  // wrong figure. Now it previews live only once the text is a complete,
  // in-range number, and clamps to the ₹10k–₹2L range on blur / Enter.
  const [draft, setDraft] = useState(() => String(budget));
  const editing = useRef(false);
  // Mirror external budget changes (slider drag, Reset) into the field — but
  // never while it's focused, so live typing isn't clobbered.
  useEffect(() => {
    if (!editing.current) setDraft(String(budget));
  }, [budget]);

  const commitBudget = (raw: string) => {
    const n = Number(raw);
    const next =
      raw.trim() === "" || Number.isNaN(n)
        ? budget
        : Math.min(BUDGET_MAX, Math.max(BUDGET_MIN, n));
    setBudget(next);
    setDraft(String(next));
  };

  // Every destination that actually receives monthly money, flattened into one
  // list. The per-fund rows further down the page are what change when the
  // budget moves, but they're off-screen while dragging — this puts the routes
  // under your thumb so the slider shows its own effect.
  const routes = basket.sleeves.flatMap((sleeve, si) =>
    sleeve.positions
      .filter((p) => p.sip_monthly > 0 && (p.mode === "core" || p.mode === "planned"))
      .map((p) => ({
        key: `${sleeve.goal_key}-${p.label}`,
        goal: sleeve.goal_name,
        color: SPLIT_COLORS[si % SPLIT_COLORS.length],
        label: p.label,
        planned: p.mode === "planned",
        amount: p.sip_monthly * scale,
      })),
  );
  return (
    <div className="mt-4 border-t border-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <label htmlFor="sip-budget" className="text-xs font-medium text-muted-foreground">
          Monthly SIP budget
        </label>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">₹</span>
          <input
            id="sip-budget"
            type="number"
            inputMode="numeric"
            min={BUDGET_MIN}
            max={BUDGET_MAX}
            step={BUDGET_STEP}
            value={draft}
            onFocus={() => {
              editing.current = true;
            }}
            onChange={(e) => {
              const raw = e.target.value;
              setDraft(raw);
              // Preview live only for a complete, in-range figure; partial or
              // over-range entries wait for blur so the funds don't jump to ₹0
              // (or the max) mid-type.
              const n = Number(raw);
              if (raw !== "" && !Number.isNaN(n) && n >= BUDGET_MIN && n <= BUDGET_MAX) {
                setBudget(n);
              }
            }}
            onBlur={() => {
              editing.current = false;
              commitBudget(draft);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
            }}
            className="w-28 rounded-lg border border-input bg-background px-2.5 py-1.5 text-right text-sm tabular-nums outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
          />
          {delta !== 0 ? (
            <button
              type="button"
              onClick={() => setBudget(planned)}
              className="rounded-md border border-input px-2 py-1 text-xs font-medium hover:bg-muted"
            >
              Reset
            </button>
          ) : null}
        </div>
      </div>
      <input
        type="range"
        min={BUDGET_MIN}
        max={BUDGET_MAX}
        step={BUDGET_STEP}
        value={budget}
        onChange={(e) => setBudget(Number(e.target.value))}
        className="mt-2 w-full accent-[var(--primary)]"
        aria-label="Monthly SIP budget"
        aria-valuetext={inr(budget)}
      />
      <div className="flex justify-between text-2xs tabular-nums text-muted-foreground">
        <span>{inr(BUDGET_MIN)}</span>
        <span>{inr(BUDGET_MAX)}</span>
      </div>
      <p className="mt-1.5 text-2xs text-muted-foreground">
        {delta === 0 ? (
          <>Your current plan. Shares stay 50/30/20 — only the amounts move.</>
        ) : (
          <>
            <span className={cn("font-medium", delta > 0 ? "text-gain" : "text-warning")}>
              {delta > 0 ? "+" : "−"}
              {inr(Math.abs(delta))}/mo
            </span>{" "}
            vs your {inr(planned)} plan — preview only, goals are unchanged. Make it real on the{" "}
            <a href="#goals" className="font-medium text-foreground underline underline-offset-2">
              Goals
            </a>{" "}
            tab.
          </>
        )}
      </p>

      {routes.length > 0 ? (
        <div className="mt-3.5 rounded-lg border border-border bg-card/50 p-3">
          <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Where {inr(budget)} lands each month
          </p>
          <ul className="mt-2 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
            {routes.map((r) => (
              <li key={r.key} className="flex min-w-0 items-baseline justify-between gap-3 text-xs">
                <span className="flex min-w-0 items-baseline gap-1.5">
                  <span
                    className="size-2 shrink-0 translate-y-[1px] rounded-full"
                    style={{ background: r.color }}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 truncate" title={`${r.goal} — ${r.label}`}>
                    {r.label}
                  </span>
                  {r.planned ? (
                    <span className="shrink-0 rounded bg-warning/15 px-1 py-px text-[10px] font-medium text-warning">
                      to set up
                    </span>
                  ) : null}
                </span>
                <span className="shrink-0 font-medium tabular-nums">{inr(r.amount)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function Sleeve({ sleeve, scale }: { sleeve: BasketSleeve; scale: number }) {
  return (
    <Panel
      title={sleeve.goal_name}
      description={sleeve.role}
      action={
        <div className="text-right text-xs text-muted-foreground">
          <div className="font-semibold tabular-nums text-foreground">
            {inr(sleeve.current_value)}
          </div>
          <div>
            {sleeve.portfolio_pct}% of portfolio · {sleeveMoneyLabel(sleeve, scale)}
          </div>
        </div>
      }
      bodyClassName="p-0 sm:p-0"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Fund</TableHead>
            <TableHead className="text-right">Value</TableHead>
            <TableHead className="hidden text-right sm:table-cell">Monthly SIP</TableHead>
            <TableHead className="text-right">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sleeve.positions.map((p) => (
            <TableRow key={`${sleeve.goal_key}-${p.label}`}>
              <TableCell className="max-w-[11rem] sm:max-w-none">
                <div className="truncate font-medium">{p.label}</div>
                <div className="truncate text-xs text-muted-foreground">{p.note}</div>
              </TableCell>
              <TableCell className="text-right tabular-nums align-top">
                {p.current_value > 0 ? inr(p.current_value) : "—"}
              </TableCell>
              <TableCell className="hidden text-right tabular-nums align-top text-muted-foreground sm:table-cell">
                {sipLabel(p.mode, p.sip_monthly * scale, p.sip_pct)}
              </TableCell>
              <TableCell className="text-right align-top">
                <span
                  className={cn(
                    "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                    MODE_META[p.mode].className,
                  )}
                >
                  {MODE_META[p.mode].label}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  );
}

/**
 * Legacy positions, framed by the decision that actually governs them.
 *
 * These are on the sell-off plan (each name exits at +{SELL_THRESHOLD_PCT}%
 * profit, hard-exit by WINDOW_END_LABEL, proceeds routed 50/30/20) — not a "reposition
 * gradually" drift. Exit status comes from the same `exitPlan` module the
 * Action Plan tab executes from, so the two pages can never disagree.
 */
function LegacyPanel({ basket, snapshot }: { basket: Basket; snapshot: Snapshot | null }) {
  const bySymbol = new Map((snapshot?.holdings ?? []).map((h) => [h.symbol, h]));

  // The sell-off plan is stock-scoped. An unassigned *mutual fund* lands in
  // `legacy` only because no goal claims it — putting a Nifty 50 index fund on
  // a sell list is the opposite of the plan, so it's split out as an
  // assignment gap instead.
  const exitItems: ExitItem[] = [];
  const unassignedFunds: { symbol: string; name: string; value: number }[] = [];
  const unknown: typeof basket.legacy = [];

  for (const l of basket.legacy) {
    const h = bySymbol.get(l.symbol);
    if (!h) {
      unknown.push(l);
    } else if (h.type === "mf") {
      unassignedFunds.push({ symbol: l.symbol, name: h.name ?? l.name, value: h.value });
    } else {
      exitItems.push(buildExitItem(h, h.last_price));
    }
  }
  const known = sortExitItems(exitItems);

  const total = known.reduce((sum, i) => sum + i.value, 0);
  const readyValue = known.filter((i) => isSellNow(i.status)).reduce((sum, i) => sum + i.value, 0);
  const months = monthsLeftLabel();

  return (
    <Panel
      title="Legacy positions"
      description={`Sell each at +${SELL_THRESHOLD_PCT}% · hard exit by ${WINDOW_END_LABEL} · proceeds routed 50/30/20.`}
      action={
        <a
          href="#action-plan"
          className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-input px-2.5 py-1.5 text-xs font-medium hover:bg-muted"
        >
          Action Plan
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </a>
      }
      bodyClassName="p-0 sm:p-0"
    >
      <div className="flex flex-wrap gap-x-8 gap-y-2 border-b border-border px-4 py-3 text-sm sm:px-5">
        <span className="tabular-nums">
          <span className="text-muted-foreground">Still to exit </span>
          <span className="font-semibold">{inr(total)}</span>
        </span>
        {readyValue > 0 ? (
          <span className="tabular-nums">
            <span className="text-muted-foreground">Ready to sell now </span>
            <span className="font-semibold text-gain">{inr(readyValue)}</span>
          </span>
        ) : null}
        <span className="tabular-nums">
          <span className="text-muted-foreground">Window closes in </span>
          <span className={cn("font-semibold", months <= 3 && "text-warning")}>{months}mo</span>
        </span>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Position</TableHead>
            <TableHead className="text-right">Value</TableHead>
            <TableHead className="hidden text-right sm:table-cell">P&amp;L</TableHead>
            <TableHead className="hidden text-right md:table-cell">To +{SELL_THRESHOLD_PCT}%</TableHead>
            <TableHead className="text-right">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {known.map((i) => (
            <TableRow key={i.symbol}>
              <TableCell className="font-medium">{i.symbol}</TableCell>
              <TableCell className="text-right tabular-nums">{inr(i.value)}</TableCell>
              <TableCell className={cn("hidden text-right tabular-nums sm:table-cell", signColor(i.pnl))}>
                {pct(i.pnlPct)}
              </TableCell>
              <TableCell className="hidden text-right md:table-cell">
                <div className="ml-auto h-1.5 w-20 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      i.progressPct >= 100 ? "bg-gain" : "bg-primary",
                    )}
                    style={{ width: `${i.progressPct}%` }}
                  />
                </div>
              </TableCell>
              <TableCell className="text-right">
                <Badge variant={EXIT_STATUS_META[i.status].variant}>
                  {EXIT_STATUS_META[i.status].label}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
          {unknown.map((l) => (
            <TableRow key={l.symbol}>
              <TableCell className="font-medium">{l.name}</TableCell>
              <TableCell className="text-right tabular-nums">{inr(l.current_value)}</TableCell>
              <TableCell className="text-right text-muted-foreground" colSpan={3}>
                Not in the latest snapshot
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <p className="border-t border-border px-4 py-3 text-2xs leading-relaxed text-muted-foreground sm:px-5">
        No new money goes into individual stocks. Growing this basket for dividend income was
        considered and rejected — a meaningful yearly income would need a large sum parked here,
        dividends are taxed at slab rate yearly (vs 12.5% LTCG on funds, only on sale), and the
        basket is flat-to-negative. Proceeds go to Travel / Vehicle / Emergency instead — FI is paused
        until 2030.
      </p>

      {unassignedFunds.length > 0 ? (
        <div className="border-t border-warning/40 bg-warning/[0.06] px-4 py-3 sm:px-5">
          <p className="text-xs font-semibold text-warning">Unassigned funds — not a sell list</p>
          <p className="mt-1 text-2xs leading-relaxed text-muted-foreground">
            These are mutual funds no goal currently claims, so they fall through to this panel.
            The exit plan covers stocks only — these need a goal, not a sale. Assign them on the{" "}
            <a href="#goals" className="font-medium text-foreground underline underline-offset-2">
              Goals
            </a>{" "}
            tab.
          </p>
          <ul className="mt-2 space-y-1">
            {unassignedFunds.map((f) => (
              <li key={f.symbol} className="flex justify-between gap-3 text-xs tabular-nums">
                <span className="min-w-0 truncate font-medium">{f.name}</span>
                <span className="shrink-0">{inr(f.value)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  );
}

export function BasketTab() {
  const state = useApi<Basket>(() => api.basket(), []);
  const snap = useApi<Snapshot>(() => api.latestSnapshot(), []);

  // null until the plan's own total arrives, so the control starts on the real
  // figure rather than snapping from a guess once data lands.
  const [budget, setBudget] = useState<number | null>(null);
  const planned = state.data?.monthly_total ?? 0;
  useEffect(() => {
    if (budget === null && planned > 0) setBudget(planned);
  }, [budget, planned]);

  const effective = budget ?? planned;
  const scale = planned > 0 ? effective / planned : 1;

  return (
    <Loadable
      state={state}
      skeleton={
        <div className="space-y-4">
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-40 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      }
      emptyMessage="No basket yet — refresh the portfolio first."
    >
      {(basket) => (
        <div className="space-y-4">
          <PageHeader
            icon={PieChart}
            title="Basket"
            subtitle="New-money routing across your plan's sleeves."
            stats={[
              { label: "Invested", value: inr(basket.total_value) },
              {
                label: "Monthly SIP",
                value: `${inr(basket.monthly_total)}/mo`,
                tone: "primary",
              },
            ]}
          />
          <div className="rounded-xl border border-border bg-gradient-to-br from-primary/[0.07] to-card p-5 shadow-sm">
            <p className="mb-4 max-w-2xl text-xs text-muted-foreground">
              Where each rupee of new SIP goes, per your plan. ELSS is held (locked-in, no new
              money); legacy stocks are being sold off, mutual funds only from here. FI is paused
              until 2030 — the Emergency Fund absorbs its share in the meantime.
            </p>
            <MonthlySplitBar basket={basket} budget={effective} />
            <BudgetControl
              budget={effective}
              setBudget={setBudget}
              planned={basket.monthly_total}
              basket={basket}
              scale={scale}
            />
          </div>

          {basket.sleeves
            .filter((s) => !PAUSED_GOAL_KEYS.has(s.goal_key))
            .map((s) => (
              <Sleeve key={s.goal_key} sleeve={s} scale={scale} />
            ))}

          {basket.sleeves.some((s) => PAUSED_GOAL_KEYS.has(s.goal_key)) ? (
            <div>
              <div className="mb-2 flex items-center gap-2 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                <span className="size-1.5 rounded-full bg-muted-foreground/50" aria-hidden="true" />
                Paused until 2030
              </div>
              <div className="space-y-4">
                {basket.sleeves
                  .filter((s) => PAUSED_GOAL_KEYS.has(s.goal_key))
                  .map((s) => (
                    <Sleeve key={s.goal_key} sleeve={s} scale={scale} />
                  ))}
              </div>
            </div>
          ) : null}

          {basket.legacy.length > 0 ? (
            <LegacyPanel basket={basket} snapshot={snap.data} />
          ) : null}
        </div>
      )}
    </Loadable>
  );
}
