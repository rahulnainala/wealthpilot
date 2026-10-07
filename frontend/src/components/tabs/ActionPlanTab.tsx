"use client";

import { useMemo, useState } from "react";
import { CircleCheck, ListChecks, Newspaper, Receipt } from "lucide-react";
import { useShallow } from "zustand/react/shallow";

import { AskAI } from "@/components/AskAI";
import { ExitedPositions, ProceedsToDeploy } from "@/components/ExitLedgerPanels";
import { PageHeader, type PageStat } from "@/components/PageHeader";
import { useLivePrice } from "@/components/LivePrice";
import { Loadable } from "@/components/Loadable";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import {
  EXIT_STATUS_META as STATUS_META,
  PROCEEDS_SPLIT,
  SELL_THRESHOLD_PCT,
  WINDOW_END_LABEL,
  buildExitItem,
  isSellNow,
  monthsLeftLabel,
  routeProceeds,
  sortExitItems,
} from "@/lib/exitPlan";
import { inr, pct, signColor } from "@/lib/format";
import { sanePrice } from "@/lib/prices";
import { severityVariant } from "@/lib/severity";
import { cn } from "@/lib/utils";
import type {
  ActionPlanItem,
  Basket,
  ExitLedger,
  Snapshot,
  SnapshotHolding,
} from "@/lib/types";
import { useTickerStore } from "@/store/useTickerStore";

function ExitRow({ h, correlated }: { h: SnapshotHolding; correlated: Set<string> }) {
  const price = useLivePrice(h.symbol, h.last_price);
  const item = buildExitItem(h, price);
  const meta = STATUS_META[item.status];
  const routes = routeProceeds(item.value);
  const [news, setNews] = useState<
    { title: string; source: string; published: string; sentiment: number }[] | null
  >(null);
  const [newsBusy, setNewsBusy] = useState(false);
  const [draft, setDraft] = useState<Awaited<ReturnType<typeof api.aiOrderDraft>> | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [placeMsg, setPlaceMsg] = useState<string | null>(null);

  async function place() {
    setPlacing(true);
    try {
      const res = await api.executeGtt(item.symbol, true);
      setPlaceMsg(
        res.status === "placed"
          ? `Placed ✓ (GTT ${res.gtt_id})`
          : (res.message ?? `Order ${res.status}.`),
      );
    } catch {
      setPlaceMsg("Placement failed — check your Zerodha session.");
    } finally {
      setPlacing(false);
      setConfirming(false);
    }
  }

  async function toggleNews() {
    if (news) {
      setNews(null);
      return;
    }
    setNewsBusy(true);
    try {
      setNews(await api.aiNews(item.symbol, 4));
    } finally {
      setNewsBusy(false);
    }
  }

  async function toggleDraft() {
    if (draft) {
      setDraft(null);
      return;
    }
    setDraftBusy(true);
    try {
      setDraft(await api.aiOrderDraft(item.symbol));
    } finally {
      setDraftBusy(false);
    }
  }

  return (
    <li className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="inline-flex items-center gap-1.5 font-medium">
          {item.symbol}
          {correlated.has(item.symbol) ? (
            <span
              title="Highly correlated with another holding — selling reduces concentration"
              className="size-1.5 rounded-full bg-warning"
            />
          ) : null}
        </span>
        <Badge variant={meta.variant}>{meta.label}</Badge>
        <AskAI
          tip="Why now?"
          question={`Should I sell ${item.symbol} now? It's at ${item.pnlPct.toFixed(1)}% P&L against my +10% sell threshold, worth ₹${Math.round(item.value)}. Consider my concentration and the ${WINDOW_END_LABEL} deadline.`}
        />
        <button
          type="button"
          onClick={() => void toggleNews()}
          disabled={newsBusy}
          aria-label={`Recent news for ${item.symbol}`}
          title="Recent news"
          className="inline-flex size-6 items-center justify-center rounded text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
        >
          <Newspaper className="size-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => void toggleDraft()}
          disabled={draftBusy}
          aria-label={`Draft a sell order for ${item.symbol}`}
          title="Draft GTT sell (review & place yourself)"
          className="inline-flex size-6 items-center justify-center rounded text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
        >
          <Receipt className="size-3.5" aria-hidden="true" />
        </button>
        <span className="ml-auto text-sm font-medium tabular-nums">
          {inr(item.value)}
        </span>
      </div>
      {draftBusy ? (
        <p className="mt-2 text-xs text-muted-foreground">Drafting order…</p>
      ) : draft ? (
        <div className="mt-2 rounded-lg border border-primary/30 bg-primary/[0.05] p-3 text-xs">
          <div className="font-semibold tabular-nums">
            {draft.side} {draft.quantity} {draft.symbol} @ trigger {inr(draft.trigger_price)}
          </div>
          <div className="mt-1 text-muted-foreground tabular-nums">
            Est. proceeds {inr(draft.est_proceeds)} →{" "}
            {draft.routing.map((r) => `${r.label} ${inr(r.amount)}`).join(" · ")}
          </div>
          <div className="mt-1 text-muted-foreground tabular-nums">
            Gain {inr(draft.gain)} · est. LTCG tax{" "}
            <span className="text-loss">{inr(draft.est_ltcg_tax)}</span>
          </div>
          <div className="mt-1 text-2xs text-muted-foreground">{draft.note}</div>
          <div className="mt-2 border-t border-border pt-2">
            {placeMsg ? (
              <p className="text-2xs text-muted-foreground">{placeMsg}</p>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="rounded text-2xs font-semibold text-loss outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                Place this GTT in Zerodha…
              </button>
            )}
          </div>

          {/* Placing a GTT is the only action here that touches the real
              account, and it was previously two 2xs inline links with no focus
              trap and no way to back out on Escape. */}
          <ConfirmDialog
            open={confirming}
            onCancel={() => setConfirming(false)}
            onConfirm={() => void place()}
            busy={placing}
            destructive
            title="Place a real order in Zerodha?"
            description="This sends a live GTT to your broker. It is not a simulation and WealthPilot cannot recall it once placed."
            confirmLabel="Place GTT"
            cancelLabel="Keep reviewing"
          >
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm tabular-nums">
              <div className="font-semibold">
                {draft.side} {draft.quantity} {draft.symbol} @ trigger {inr(draft.trigger_price)}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                Est. proceeds {inr(draft.est_proceeds)} · gain {inr(draft.gain)} · est. LTCG tax{" "}
                {inr(draft.est_ltcg_tax)}
              </div>
            </div>
          </ConfirmDialog>
        </div>
      ) : null}
      {newsBusy ? (
        <p className="mt-2 text-xs text-muted-foreground">Fetching recent headlines…</p>
      ) : news ? (
        <div className="mt-2 border-l-2 border-border pl-3">
          {news.length === 0 ? (
            <p className="text-xs text-muted-foreground">No recent headlines found.</p>
          ) : (
            <>
              {(() => {
                const avg = news.reduce((s, n) => s + n.sentiment, 0) / news.length;
                const label = avg > 0.15 ? "positive" : avg < -0.15 ? "negative" : "neutral";
                const tone =
                  label === "positive"
                    ? "text-gain"
                    : label === "negative"
                      ? "text-loss"
                      : "text-muted-foreground";
                return (
                  <p className={cn("mb-1.5 text-2xs font-semibold uppercase tracking-[0.14em]", tone)}>
                    News mood: {label} ({avg >= 0 ? "+" : ""}
                    {avg.toFixed(2)})
                  </p>
                );
              })()}
              <ul className="space-y-1">
                {news.map((n) => (
                  <li key={n.title} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                    <span
                      className={cn(
                        "mt-1 size-1.5 shrink-0 rounded-full",
                        n.sentiment > 0.1
                          ? "bg-gain"
                          : n.sentiment < -0.1
                            ? "bg-loss"
                            : "bg-muted-foreground/50",
                      )}
                      aria-hidden="true"
                    />
                    <span>
                      {n.title}
                      <span className="text-2xs opacity-70"> · {n.source}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      ) : null}
      <div className="mt-3 flex items-center gap-3">
        <Progress
          value={item.progressPct}
          aria-hidden="true"
          className="h-1.5 flex-1"
          indicatorClassName={cn(
            "motion-reduce:transition-none",
            item.status === "ready" && "bg-gain",
            item.status === "deadline" && "bg-loss",
          )}
        />
        <span className="w-32 shrink-0 text-right text-sm tabular-nums">
          <span className={signColor(item.pnl)}>{pct(item.pnlPct)}</span>
          <span className="text-muted-foreground"> of +{SELL_THRESHOLD_PCT}%</span>
        </span>
      </div>
      <p className="mt-2 text-xs tabular-nums text-muted-foreground">
        On sale: {routes.map((r) => `${r.label} ${inr(r.amount)}`).join(" · ")}
      </p>
    </li>
  );
}

function OtherActions() {
  const state = useApi<ActionPlanItem[]>(() => api.actionPlan(), []);
  return (
    <Panel
      title="Other Actions"
      description="Portfolio issues detected outside the sell-off plan."
      bodyClassName="p-0 sm:p-0"
    >
      <Loadable state={state} skeleton={<Skeleton className="m-5 h-24" />}>
        {(items) =>
          items.length === 0 ? (
            <p className="px-5 py-4 text-sm text-muted-foreground">
              Nothing else to act on right now.
            </p>
          ) : (
            <ol className="divide-y divide-border">
              {items.map((item) => (
                <li key={`${item.code}-${item.priority}`} className="flex gap-3 px-5 py-4">
                  <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold">
                    {item.priority}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{item.title}</span>
                      <Badge variant={severityVariant(item.severity)}>
                        {item.severity}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{item.action}</p>
                    {item.amount != null ? (
                      <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                        {inr(item.amount)}
                        {item.symbols.length ? ` · ${item.symbols.join(", ")}` : ""}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          )
        }
      </Loadable>
    </Panel>
  );
}

function ExitPlanView({ snapshot, basket }: { snapshot: Snapshot; basket: Basket }) {
  const div = useApi(() => api.diversification(), []);
  const ledgerState = useApi<ExitLedger>(() => api.exitLedger(), []);
  const ledger = ledgerState.data;
  const correlated = new Set(
    (div.data?.top_pairs ?? [])
      .filter((p) => Math.abs(p.correlation) >= 0.6)
      .flatMap((p) => [p.label_a, p.label_b]),
  );
  const legacy = useMemo(() => {
    const legacySymbols = new Set(basket.legacy.map((l) => l.symbol));
    return snapshot.holdings.filter(
      (h) => h.type === "stock" && legacySymbols.has(h.symbol),
    );
  }, [snapshot, basket]);

  // Aggregate over live prices; useShallow keeps re-renders limited to real
  // value changes (the same discipline as OverviewTab's derived selector).
  const totals = useTickerStore(
    useShallow((s) => {
      let value = 0;
      let invested = 0;
      let readyCount = 0;
      let readyValue = 0;
      for (const h of legacy) {
        const item = buildExitItem(h, sanePrice(h.last_price, s.ticks[h.symbol]?.ltp));
        value += item.value;
        invested += item.invested;
        if (isSellNow(item.status)) {
          readyCount += 1;
          readyValue += item.value;
        }
      }
      return { value, invested, readyCount, readyValue };
    }),
  );

  const sorted = useTickerStore(
    useShallow((s) =>
      sortExitItems(
        legacy.map((h) =>
          buildExitItem(h, sanePrice(h.last_price, s.ticks[h.symbol]?.ltp)),
        ),
      ).map((i) => i.symbol),
    ),
  );
  const bySymbol = new Map(legacy.map((h) => [h.symbol, h]));

  const pnl = totals.value - totals.invested;
  const pnlPct = totals.invested ? (pnl / totals.invested) * 100 : 0;
  const monthsLeft = monthsLeftLabel();

  // Headline numbers ride in the page header — matching every other tab — so the
  // sell queue itself sits higher on the page instead of below a KPI-card band.
  const stats: PageStat[] | undefined =
    legacy.length > 0
      ? [
          {
            label: "To exit",
            value: inr(totals.value),
            hint: `${legacy.length} position${legacy.length === 1 ? "" : "s"}`,
          },
          {
            label: "Ready now",
            value: totals.readyCount > 0 ? inr(totals.readyValue) : "—",
            tone: totals.readyCount > 0 ? "gain" : "default",
            hint: `${totals.readyCount}/${legacy.length} at +${SELL_THRESHOLD_PCT}%`,
          },
          {
            label: "Unrealized P&L",
            value: inr(pnl),
            tone: pnl >= 0 ? "gain" : "loss",
            hint: pct(pnlPct),
          },
          // Only once something has actually been sold — an empty "Realized ₹0"
          // slot would read as a loss of information, not progress.
          ...(ledger && ledger.exits.length > 0
            ? ([
                {
                  label: "Realized",
                  value: inr(ledger.realized_pnl),
                  tone: ledger.realized_pnl >= 0 ? "gain" : "loss",
                  hint: `${ledger.exited_count} exited`,
                },
              ] satisfies PageStat[])
            : []),
        ]
      : undefined;

  const header = (
    <PageHeader
      icon={ListChecks}
      title="Action Plan"
      subtitle="The sell-off queue and where the proceeds go — driven by the same exit plan the Basket reads."
      stats={stats}
    />
  );

  const ledgerPanels = ledger ? (
    <>
      <ProceedsToDeploy ledger={ledger} onChange={() => void ledgerState.reload()} />
      <ExitedPositions ledger={ledger} />
    </>
  ) : null;

  if (legacy.length === 0) {
    return (
      <div className="space-y-4">
        {header}
        {ledgerPanels}
        <Panel title="Sell-Off Plan">
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <CircleCheck className="size-8 text-gain" aria-hidden="true" />
            <p className="font-medium">Repositioning complete</p>
            <p className="max-w-md text-sm text-muted-foreground">
              Every legacy position has been exited. New money flows through the
              goal SIPs — nothing left to sell.
            </p>
          </div>
        </Panel>
        <OtherActions />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {header}
      {/* Money already freed outranks money still to free: idle proceeds are a
          decision waiting on the owner, the queue is a decision waiting on the
          market. */}
      {ledgerPanels}
      <Panel
        title="Sell Queue"
        description={`Legacy REIT & PSU positions — sell at +${SELL_THRESHOLD_PCT}% profit, everything exits by ${WINDOW_END_LABEL} (${monthsLeft} months left). Sorted by readiness.`}
      >
        <ol className="space-y-3">
          {sorted.map((symbol) => {
            const h = bySymbol.get(symbol);
            return h ? <ExitRow key={symbol} h={h} correlated={correlated} /> : null;
          })}
        </ol>
      </Panel>

      {/* Forward-looking: what the *unsold* remainder would route to. Distinct
          from "Proceeds to Deploy" above, which is real money already in hand. */}
      <Panel
        title="Projected Routing"
        description="Where the rest would go once sold — the plan's split applied to the legacy value still held."
      >
        <div className="grid gap-4 sm:grid-cols-3">
          {routeProceeds(totals.value).map((route, i) => (
            <div key={route.label} className="rounded-lg border border-border p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{route.label}</span>
                <Badge variant="outline">{route.pct}%</Badge>
              </div>
              <div className="mt-1 text-xl font-semibold tabular-nums">
                {inr(route.amount)}
              </div>
              <ul className="mt-3 space-y-1.5">
                {PROCEEDS_SPLIT[i].funds.map((fund, j) => (
                  <li
                    key={fund.name}
                    className="flex items-center justify-between gap-2 text-xs"
                  >
                    <span className="min-w-0 truncate text-muted-foreground">
                      {fund.name}
                    </span>
                    <span className="shrink-0 tabular-nums">
                      {inr(route.funds[j].amount)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Panel>

      <OtherActions />
    </div>
  );
}

export function ActionPlanTab({ snapshot }: { snapshot: Snapshot }) {
  const basket = useApi<Basket>(() => api.basket(), []);
  return (
    <Loadable
      state={basket}
      skeleton={
        <div className="space-y-4">
          <Skeleton className="h-16 rounded-xl" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-80 rounded-xl" />
        </div>
      }
    >
      {(b) => <ExitPlanView snapshot={snapshot} basket={b} />}
    </Loadable>
  );
}
