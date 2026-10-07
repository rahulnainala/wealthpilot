import type { SnapshotHolding } from "@/lib/types";

/**
 * Legacy sell-off plan — the single source of truth for exit status, shared by
 * the Action Plan tab (which executes from it) and the Basket tab (which
 * reports against it), so the two can never disagree.
 *
 * Scope is **stocks only**: the unassigned REIT/PSU/commodity positions. They
 * get no new money and each exits once it reaches the profit threshold;
 * anything still held near the window's end exits regardless of P&L, which is
 * what stops a tactical "wait for +10%" from drifting indefinitely. Proceeds
 * follow the monthly SIP split (50/30/20 Travel/Vehicle/Emergency — Emergency
 * stands in for FI, which is paused until 2030; see below).
 *
 * Chosen over the alternative of growing the basket for dividend income. FI's
 * share moved to the Emergency Fund while FI is paused — same treatment as the
 * monthly SIP, for consistency.
 */

export const SELL_THRESHOLD_PCT = 10;
export const NEAR_THRESHOLD_PCT = 7;

/**
 * Repositioning window: plan date → outer deadline.
 *
 * Pulled in from 2027-12-21 to 2027-06-21 on 2026-08-02. The +10% trigger does
 * the work for winners and this backstop does it for losers, so the date is
 * what actually decides how long correlated PSU/REIT exposure is carried —
 * several names are underwater and will never reach +10% before it. Halving
 * the remaining window still leaves ~3 quarters for the trigger to fire.
 *
 * WINDOW_END_LABEL exists so no screen ever hardcodes the month again. The
 * date used to be duplicated as prose in nine user-visible strings across both
 * apps, which meant moving it silently left every label describing the old one.
 */
export const WINDOW_START = new Date("2026-06-21T00:00:00+05:30");
export const WINDOW_END = new Date("2027-06-21T00:00:00+05:30");

/** Human label for WINDOW_END, e.g. "Jun 2027". Derive, never retype. */
export const WINDOW_END_LABEL = WINDOW_END.toLocaleDateString("en-IN", {
  month: "short",
  year: "numeric",
  timeZone: "Asia/Kolkata",
});
/** Within this many months of the deadline, unsold positions are flagged. */
export const DEADLINE_URGENCY_MONTHS = 3;

const MS_PER_MONTH = 1000 * 60 * 60 * 24 * 30.44;

export type ExitStatus = "ready" | "near" | "hold" | "deadline";

/** Badge label/variant per status — shared so Basket and Action Plan render it identically. */
export const EXIT_STATUS_META: Record<
  ExitStatus,
  { label: string; variant: "success" | "warning" | "outline" | "critical" }
> = {
  ready: { label: "Sell now", variant: "success" },
  near: { label: "Approaching", variant: "warning" },
  hold: { label: "Hold", variant: "outline" },
  deadline: { label: "Deadline — sell", variant: "critical" },
};

export interface ExitItem {
  symbol: string;
  name: string;
  qty: number;
  value: number;
  invested: number;
  pnl: number;
  pnlPct: number;
  /** Progress toward the sell threshold, clamped 0–100. */
  progressPct: number;
  status: ExitStatus;
}

export interface GoalRoute {
  key: string;
  label: string;
  pct: number;
  funds: { name: string; pct: number }[];
}

/** Proceeds routing = the plan's monthly split (Travel/Vehicle/Emergency 50/30/20). */
export const PROCEEDS_SPLIT: GoalRoute[] = [
  {
    key: "travel",
    label: "Travel",
    pct: 50,
    funds: [
      { name: "UTI Nifty 50 Index", pct: 60 },
      { name: "Parag Parikh Flexi Cap", pct: 40 },
    ],
  },
  {
    key: "vehicle",
    label: "Vehicle",
    pct: 30,
    funds: [
      { name: "Nippon Midcap 150", pct: 50 },
      { name: "Zerodha Nifty 50 Index", pct: 50 },
    ],
  },
  {
    key: "emergency",
    label: "Emergency Fund",
    pct: 20,
    funds: [{ name: "HDFC Short Term Debt", pct: 100 }],
  },
];

export function monthsRemaining(now: Date = new Date()): number {
  return Math.max(0, (WINDOW_END.getTime() - now.getTime()) / MS_PER_MONTH);
}

/**
 * Whole months left, for display. Centralised because the Action Plan and
 * Basket tabs both surface it — rounding independently (ceil vs round) had
 * them stating "18mo" and "17mo" for the same deadline.
 */
export function monthsLeftLabel(now: Date = new Date()): number {
  return Math.round(monthsRemaining(now));
}

/**
 * Whether a position should be sold on this pass.
 *
 * `deadline` counts alongside `ready`: past the urgency cutoff a position
 * exits regardless of P&L, so omitting it would report "0 ready to sell" on
 * exactly the run where everything must go.
 */
export function isSellNow(status: ExitStatus): boolean {
  return status === "ready" || status === "deadline";
}

/** How far through the exit window we are, clamped 0–100. */
export function windowElapsedPct(now: Date = new Date()): number {
  const total = WINDOW_END.getTime() - WINDOW_START.getTime();
  const elapsed = now.getTime() - WINDOW_START.getTime();
  return Math.max(0, Math.min(100, (elapsed / total) * 100));
}

export function exitStatus(pnlPct: number, now: Date = new Date()): ExitStatus {
  if (pnlPct >= SELL_THRESHOLD_PCT) return "ready";
  if (monthsRemaining(now) <= DEADLINE_URGENCY_MONTHS) return "deadline";
  if (pnlPct >= NEAR_THRESHOLD_PCT) return "near";
  return "hold";
}

export function buildExitItem(
  h: SnapshotHolding,
  livePrice: number,
  now: Date = new Date(),
): ExitItem {
  const value = h.qty * livePrice;
  const invested = h.qty * h.avg_price;
  const pnl = value - invested;
  const pnlPct = invested ? (pnl / invested) * 100 : 0;
  return {
    symbol: h.symbol,
    name: h.name ?? h.symbol,
    qty: h.qty,
    value,
    invested,
    pnl,
    pnlPct,
    progressPct: Math.max(0, Math.min(100, (pnlPct / SELL_THRESHOLD_PCT) * 100)),
    status: exitStatus(pnlPct, now),
  };
}

const STATUS_RANK: Record<ExitStatus, number> = {
  ready: 0,
  deadline: 1,
  near: 2,
  hold: 3,
};

/** Most actionable first: ready → deadline → near → hold, then by P&L%. */
export function sortExitItems(items: ExitItem[]): ExitItem[] {
  return [...items].sort(
    (a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status] || b.pnlPct - a.pnlPct,
  );
}

export interface RoutedProceeds {
  label: string;
  pct: number;
  amount: number;
  funds: { name: string; amount: number }[];
}

/** Split a sale amount across the plan's destinations. */
export function routeProceeds(amount: number): RoutedProceeds[] {
  return PROCEEDS_SPLIT.map((goal) => {
    const goalAmount = (amount * goal.pct) / 100;
    return {
      label: goal.label,
      pct: goal.pct,
      amount: goalAmount,
      funds: goal.funds.map((f) => ({
        name: f.name,
        amount: (goalAmount * f.pct) / 100,
      })),
    };
  });
}
