"use client";

import { useState } from "react";
import { CheckCircle2, CircleDollarSign } from "lucide-react";

import { Panel } from "@/components/Panel";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { routeProceeds } from "@/lib/exitPlan";
import { dateOnly, inr, inrPrecise, pct, signColor } from "@/lib/format";
import type { ExitLedger } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Positions the sell-off has already cleared.
 *
 * The sell queue only ever shows what is still held, so a completed sale used
 * to vanish without trace — no progress, no realized P&L, nothing to confirm
 * the plan is being followed. These are struck through rather than hidden:
 * the point is to see the plan being worked down.
 */
export function ExitedPositions({ ledger }: { ledger: ExitLedger }) {
  if (ledger.exits.length === 0) return null;

  const total = ledger.exited_count + ledger.remaining_count;
  const donePct = total > 0 ? (ledger.exited_count / total) * 100 : 0;

  return (
    <Panel
      title="Exited"
      description="Sales detected from your holdings history. Prices are the last the app saw before the shares left — estimates, not broker fills."
    >
      <div className="mb-4 flex items-center gap-3">
        <Progress
          value={donePct}
          aria-hidden="true"
          className="h-1.5 flex-1"
          indicatorClassName="bg-gain motion-reduce:transition-none"
        />
        <span className="shrink-0 text-sm tabular-nums">
          <span className="font-medium">
            {ledger.exited_count}/{total}
          </span>
          <span className="text-muted-foreground"> exited</span>
        </span>
      </div>

      <ul className="space-y-2">
        {ledger.exits.map((exit) => (
          <li
            key={exit.id}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-muted/20 px-4 py-3"
          >
            <CheckCircle2 className="size-4 shrink-0 text-gain" aria-hidden="true" />
            {/* The check glyph and the strike-through both carry "this is done"
                visually only; the state has to survive into the a11y tree too. */}
            <span className="sr-only">Exited:</span>
            <span className="font-medium text-muted-foreground line-through decoration-muted-foreground/40">
              {exit.symbol}
            </span>
            {exit.full_exit ? null : <Badge variant="outline">Partial</Badge>}
            <span className="text-xs text-muted-foreground tabular-nums">
              {exit.qty} @ ~{inrPrecise(exit.exit_price)} · {dateOnly(exit.exited_on)}
            </span>
            <span className="ml-auto flex items-center gap-3 text-sm tabular-nums">
              <span className={signColor(exit.realized_pnl)}>
                {inr(exit.realized_pnl)} ({pct(exit.realized_pnl_pct)})
              </span>
              <span className="font-medium">{inr(exit.proceeds)}</span>
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-xs tabular-nums text-muted-foreground">
        Realized so far:{" "}
        <span className={cn("font-medium", signColor(ledger.realized_pnl))}>
          {inr(ledger.realized_pnl)}
        </span>{" "}
        on {inr(ledger.proceeds_total)} of proceeds.
      </p>
    </Panel>
  );
}

/**
 * Sale money that has not yet been put back to work.
 *
 * Proceeds landing as idle cash is the quiet failure mode of a staged sell-off:
 * the hard part (selling at the threshold) is done, and then the money sits
 * earning nothing because nothing was tracking it.
 */
export function ProceedsToDeploy({
  ledger,
  onChange,
}: {
  ledger: ExitLedger;
  onChange: () => void;
}) {
  const [busyId, setBusyId] = useState<number | null>(null);
  // Marking one deployed removes its row and re-totals the panel; without an
  // announcement a screen reader user gets silence and a vanished control.
  const [announcement, setAnnouncement] = useState("");
  const pending = ledger.exits.filter((e) => e.deployed_at === null);

  async function markDeployed(id: number, symbol: string) {
    setBusyId(id);
    try {
      await api.markExitDeployed(id, true);
      setAnnouncement(`${symbol} proceeds marked as deployed.`);
      onChange();
    } finally {
      setBusyId(null);
    }
  }

  if (pending.length === 0) return null;

  const routes = routeProceeds(ledger.undeployed_amount);

  return (
    <Panel
      title="Proceeds to Deploy"
      description="Cash from completed sales, still uninvested. Move it into the goal funds, then mark it done."
      className="border-warning/40"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {/* Baseline alignment puts a replaced element's *bottom* on the text
            baseline, so the 20px coin overshoots the digits' 17px cap height
            and rides ~1.5px high. Nudge a whole pixel down — a half-pixel
            transform would just blur the glyph. */}
        <CircleDollarSign
          className="size-5 translate-y-px text-warning"
          aria-hidden="true"
        />
        <span className="text-2xl font-semibold tabular-nums">
          {inr(ledger.undeployed_amount)}
        </span>
        <span className="text-sm text-muted-foreground">
          from {pending.length} sale{pending.length === 1 ? "" : "s"}, sitting idle
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {routes.map((route) => (
          <div key={route.label} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{route.label}</span>
              <Badge variant="outline">{route.pct}%</Badge>
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {inr(route.amount)}
            </div>
            <ul className="mt-2 space-y-1">
              {route.funds.map((fund) => (
                <li
                  key={fund.name}
                  className="flex items-center justify-between gap-2 text-2xs"
                >
                  <span className="min-w-0 truncate text-muted-foreground">
                    {fund.name}
                  </span>
                  <span className="shrink-0 tabular-nums">{inr(fund.amount)}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <ul className="mt-4 divide-y divide-border border-t border-border">
        {pending.map((exit) => (
          <li
            key={exit.id}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-sm"
          >
            <span className="font-medium">{exit.symbol}</span>
            <span className="text-xs text-muted-foreground tabular-nums">
              sold {dateOnly(exit.exited_on)}
            </span>
            <span className="ml-auto tabular-nums">{inr(exit.proceeds)}</span>
            {/* Every row's visible label is identical, so the accessible name
                carries the symbol — otherwise a button list is N × "Mark
                deployed" with no way to tell them apart. min-h-6 meets the
                24px target minimum that text-2xs + py-1 (22px) misses. */}
            <button
              type="button"
              onClick={() => void markDeployed(exit.id, exit.symbol)}
              disabled={busyId === exit.id}
              aria-label={`Mark ${exit.symbol} proceeds as deployed`}
              className="inline-flex min-h-6 items-center rounded px-2 py-1 text-2xs font-semibold text-primary outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
            >
              {busyId === exit.id ? "Marking…" : "Mark deployed"}
            </button>
          </li>
        ))}
      </ul>

      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </Panel>
  );
}
