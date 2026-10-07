"use client";

import dynamic from "next/dynamic";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { AiBriefPanel } from "@/components/AiBriefPanel";
import { NeedsAttention } from "@/components/NeedsAttention";
import { PilotInsights } from "@/components/PilotInsights";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { GoalsGlance } from "@/components/GoalsGlance";
import { CHART_GAIN, CHART_LOSS } from "@/components/charts/chartColors";
import { Panel } from "@/components/Panel";
import { Tooltip } from "@/components/ui/tooltip";
import { BUCKETS, bucketColor } from "@/lib/buckets";
import { dateOnly, inr, istDateKey, pct, signColor } from "@/lib/format";
import { sanePrice } from "@/lib/prices";
import { cn } from "@/lib/utils";
import type { PortfolioRisk, Snapshot } from "@/lib/types";
import { useTickerStore } from "@/store/useTickerStore";

// Chart.js is heavy (~150 kB) and Overview is the one statically-imported tab —
// so its charts load on demand instead of shipping in the first-load bundle.
// The hero number, day change, attention band and allocation *table* render
// immediately; the canvases stream in behind a same-size placeholder (parents
// reserve the height, so there's no layout shift).
const Sparkline = dynamic(
  () => import("@/components/charts/Sparkline").then((m) => m.Sparkline),
  {
    ssr: false,
    loading: () => (
      <div className="h-10 w-full animate-pulse rounded bg-muted/40 motion-reduce:animate-none" />
    ),
  },
);
const AllocationDonut = dynamic(
  () => import("@/components/charts/AllocationDonut").then((m) => m.AllocationDonut),
  {
    ssr: false,
    loading: () => (
      <div className="size-full animate-pulse rounded-full bg-muted/40 motion-reduce:animate-none" />
    ),
  },
);

const BREAKDOWN_ORDER = ["growth", "dividend", "mf", "other", "cash"] as const;
// The ~⅓ target the three core buckets are steered toward (growth/dividend/mf).
const CORE_TARGET = 33.3;
const CORE_BUCKETS = new Set(["growth", "dividend", "mf"]);

/** A single cockpit readout in the hero's vitals strip. */
function Vital({
  label,
  value,
  tip,
  valueClass,
}: {
  label: string;
  value: React.ReactNode;
  tip: string;
  valueClass?: string;
}) {
  return (
    <Tooltip label={tip} side="bottom">
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </span>
        <span className={cn("text-sm font-medium tabular-nums", valueClass)}>{value}</span>
      </div>
    </Tooltip>
  );
}

/**
 * The account hero: the one number that matters, its day change, a value
 * trend, the supporting figures (invested / P&L / cash) and a slim cockpit
 * vitals strip (heading + risk readouts). It is now the single "state of the
 * account" card — the old standalone instruments row folded up into here, so
 * the Overview leads with one confident focal point instead of stacking a hero
 * and a separate readouts panel.
 */
function PortfolioHero({
  total,
  invested,
  pnl,
  pnlPct,
  cash,
  dayDelta,
  dayPct,
  sinceTs,
  trend,
  heading,
  risk,
}: {
  total: number;
  invested: number;
  pnl: number;
  pnlPct: number;
  cash: number;
  dayDelta: number | null;
  dayPct: number | null;
  sinceTs: string | null;
  trend: number[];
  heading: string;
  risk: PortfolioRisk | null;
}) {
  const up = dayDelta == null ? null : dayDelta >= 0;
  const trendUp = trend.length >= 2 ? trend[trend.length - 1] >= trend[0] : true;

  return (
    <section
      aria-label="Portfolio summary"
      className="overflow-hidden rounded-xl border border-border bg-gradient-to-br from-primary/[0.08] via-card to-card shadow-sm"
    >
      <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Total portfolio value
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="text-3xl font-bold leading-none tracking-tight tabular-nums sm:text-4xl">
              {inr(total)}
            </span>
            {up == null ? (
              <span className="text-sm text-muted-foreground">Live</span>
            ) : (
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums",
                  up ? "bg-gain/10 text-gain" : "bg-loss/10 text-loss",
                )}
              >
                {up ? (
                  <ArrowUpRight className="size-4" aria-hidden="true" />
                ) : (
                  <ArrowDownRight className="size-4" aria-hidden="true" />
                )}
                {up ? "+" : ""}
                {inr(dayDelta!)}
                <span className="font-medium opacity-80">{pct(dayPct)}</span>
              </span>
            )}
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">
            {sinceTs
              ? `Change since ${dateOnly(sinceTs)}`
              : "No earlier snapshot yet to compare against"}
          </p>
        </div>

        <dl className="flex flex-wrap gap-x-6 gap-y-3 sm:justify-end">
          <div>
            <dt className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Invested
            </dt>
            <dd className="mt-1 text-lg font-semibold leading-none tabular-nums">{inr(invested)}</dd>
          </div>
          <div>
            <dt className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Unrealized P&amp;L
            </dt>
            <dd className={cn("mt-1 text-lg font-semibold leading-none tabular-nums", signColor(pnl))}>
              {inr(pnl)} <span className="text-xs font-medium">{pct(pnlPct)}</span>
            </dd>
          </div>
          <div>
            <dt className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Cash
            </dt>
            <dd className="mt-1 text-lg font-semibold leading-none tabular-nums">{inr(cash)}</dd>
          </div>
        </dl>
      </div>

      {/* Vitals strip: heading (allocation split) + the engine's risk readouts.
          Altitude / vertical-speed (value & day change) lead above, so they are
          intentionally not repeated here. */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1.5 border-t border-border/60 px-5 py-3">
        <Vital label="Hdg" value={heading} tip="Heading — growth/dividend/MF split (target ⅓ each)" />
        {risk ? (
          <>
            <Vital label="VaR" value={inr(risk.var)} valueClass="text-loss" tip="1-day loss exceeded only 5% of days" />
            <Vital label="Vol" value={`${(risk.annual_volatility * 100).toFixed(1)}%`} tip="Annualized portfolio volatility" />
            <Vital label="DD" value={`−${(risk.max_drawdown * 100).toFixed(1)}%`} tip="Worst peak-to-trough over 3 months" />
          </>
        ) : null}
        <a
          href="#risk"
          className="ml-auto hidden text-2xs font-medium uppercase tracking-[0.14em] text-muted-foreground hover:text-primary sm:inline"
        >
          Risk detail <span aria-hidden="true">→</span>
        </a>
      </div>

      {trend.length >= 2 ? (
        <div className="border-t border-border/60 px-5 pb-3 pt-3">
          <div className="mb-1 flex items-center justify-between text-2xs uppercase tracking-[0.14em] text-muted-foreground">
            <span>Value trend</span>
            <span className="tabular-nums">last {trend.length} snapshots</span>
          </div>
          <Sparkline data={trend} color={trendUp ? CHART_GAIN : CHART_LOSS} />
        </div>
      ) : null}
    </section>
  );
}

/**
 * The allocation breakdown beside the donut — the rupee value, share, and (for
 * the three core buckets) drift from the ⅓ target in one place. This table +
 * the donut are now the *single* allocation view on the Overview: the old
 * standalone "vs ⅓" bar chart was a third read of the same data and has been
 * dropped in favour of the drift column here.
 */
function AllocationBreakdown({
  bucketValues,
  cash,
  total,
}: {
  bucketValues: Record<string, number>;
  cash: number;
  total: number;
}) {
  const values: Record<string, number> = { ...bucketValues, cash };
  const rows = BREAKDOWN_ORDER.map((k) => {
    const value = values[k] ?? 0;
    return {
      key: k,
      label: BUCKETS[k].label,
      color: bucketColor(k),
      value,
      share: total > 0 ? (value / total) * 100 : 0,
      drift: CORE_BUCKETS.has(k) ? (total > 0 ? (value / total) * 100 : 0) - CORE_TARGET : null,
    };
  }).filter((r) => r.value > 0);

  return (
    <div className="min-w-0">
      <div className="flex items-center gap-3 border-b border-border pb-1.5 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        <span className="flex-1">Sleeve</span>
        <span className="w-28 text-right">Value</span>
        <span className="w-9 text-right">%</span>
        <span className="w-14 text-right">vs ⅓</span>
      </div>
      <ul className="mt-1.5 space-y-2">
        {rows.map((r) => {
          // Round first, then sign — so a share sitting on the target reads a
          // clean "0pt" instead of "+0pt"/"−0pt", and drift uses the same U+2212
          // minus glyph as the rest of the app.
          const drift = r.drift == null ? null : Math.round(r.drift);
          return (
            <li key={r.key} className="flex items-center gap-3 text-sm">
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ background: r.color }}
                aria-hidden="true"
              />
              <span className="min-w-0 flex-1 truncate">{r.label}</span>
              <span className="w-28 shrink-0 text-right font-medium tabular-nums">{inr(r.value)}</span>
              <span className="w-9 shrink-0 text-right tabular-nums text-muted-foreground">
                {r.share.toFixed(0)}
              </span>
              <span className="w-14 shrink-0 text-right text-2xs tabular-nums">
                {drift == null ? (
                  <span className="text-muted-foreground/50">—</span>
                ) : (
                  <span className={Math.abs(drift) < 3 ? "text-muted-foreground" : "text-warning"}>
                    {drift > 0 ? "+" : drift < 0 ? "−" : ""}
                    {Math.abs(drift)}pt
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function OverviewTab({ snapshot }: { snapshot: Snapshot }) {
  // Select the derived aggregate, not the ticks map: the store creates a new
  // `ticks` object on every websocket tick, but this number only changes when
  // a relevant price actually moves — so the tab re-renders on value changes,
  // not on tick traffic.
  const stockValue = useTickerStore((s) =>
    snapshot.holdings
      .filter((h) => h.type === "stock")
      .reduce(
        (sum, h) => sum + h.qty * sanePrice(h.last_price, s.ticks[h.symbol]?.ltp),
        0,
      ),
  );

  const mfValue = snapshot.holdings
    .filter((h) => h.type === "mf")
    .reduce((sum, h) => sum + h.value, 0);

  const total = stockValue + mfValue + snapshot.cash;
  const pnl = total - snapshot.invested;
  const pnlPct = snapshot.invested ? (pnl / snapshot.invested) * 100 : 0;

  // Day change: the live total against the most recent snapshot from a *prior*
  // IST day. Taking `.at(-2)` instead only works when today's snapshot already
  // exists — before the 09:45 tick (or on any day the scheduler missed) it
  // silently reaches back an extra day and still calls the result a day change.
  // Weekends leave real gaps, so the baseline's own date is shown rather than
  // implied.
  const history = useApi(() => api.snapshotHistory(30), []);
  const risk = useApi(() => api.portfolioRisk(), []);
  const todayKey = istDateKey(new Date());
  const prev = (history.data ?? []).filter((h) => istDateKey(h.ts) < todayKey).at(-1);
  const dayDelta = prev ? total - prev.total_value : null;
  const dayPct = prev && prev.total_value > 0 ? ((total - prev.total_value) / prev.total_value) * 100 : null;
  const trend = (history.data ?? []).map((s) => s.total_value);

  const hdg = ["growth", "dividend", "mf"]
    .map((k) => (total > 0 ? Math.round(((snapshot.bucket_values[k] ?? 0) / total) * 100) : 0))
    .join("/");

  return (
    <div className="space-y-4">
      <PortfolioHero
        total={total}
        invested={snapshot.invested}
        pnl={pnl}
        pnlPct={pnlPct}
        cash={snapshot.cash}
        dayDelta={dayDelta}
        dayPct={dayPct}
        sinceTs={prev?.ts ?? null}
        trend={trend}
        heading={hdg}
        risk={risk.data ?? null}
      />

      {/* AI watch-alerts: dismissible, renders nothing on the happy path. */}
      <PilotInsights />

      {/* The single "does anything need me?" band — deterministic issues +
          action-plan to-dos, deep-linked to where they get fixed. */}
      <NeedsAttention />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Current Allocation"
          description="Where your capital sits — and how the core buckets drift from ⅓ each."
        >
          {/* Container-query, not viewport: these two panels sit two-up on
              desktop, so each is only ~400px wide — too narrow for a 160px donut
              *and* the table's sleeve labels side by side (the labels would
              collapse to 0 and vanish). Stack donut-over-table until the panel
              itself is wide enough (single-column / ultra-wide), only then place
              them side by side. */}
          <div className="@container">
            <div className="grid grid-cols-1 items-center gap-5 @[28rem]:grid-cols-[10rem_minmax(0,1fr)]">
              <div className="mx-auto h-40 w-40 @[28rem]:mx-0">
                <AllocationDonut
                  bucketValues={snapshot.bucket_values}
                  cash={snapshot.cash}
                  showLegend={false}
                />
              </div>
              <AllocationBreakdown
                bucketValues={snapshot.bucket_values}
                cash={snapshot.cash}
                total={total}
              />
            </div>
          </div>
        </Panel>

        <GoalsGlance />
      </div>

      <AiBriefPanel />
    </div>
  );
}
