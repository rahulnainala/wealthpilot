"use client";

import { BarChart3 } from "lucide-react";
import { useShallow } from "zustand/react/shallow";

import { CHART_GAIN, CHART_LOSS } from "@/components/charts/chartColors";
import { Sparkline } from "@/components/charts/Sparkline";
import { MacroTab } from "@/components/tabs/MacroTab";
import { PageHeader, type PageStat } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { Loadable } from "@/components/Loadable";
import { Card, CardContent } from "@/components/ui/card";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { inrPrecise, pct, signColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { MarketOverview } from "@/lib/types";
import { useTickerStore } from "@/store/useTickerStore";

function IndexCard({
  name,
  lastPrice,
  changePct,
}: {
  name: string;
  lastPrice: number;
  changePct: number;
}) {
  const tick = useTickerStore((s) => s.ticks[name]);
  const history = useTickerStore((s) => s.history[name]);

  const price = tick?.ltp ?? lastPrice;
  const change = tick?.change_pct ?? changePct;
  const up = change >= 0;
  const color = up ? CHART_GAIN : CHART_LOSS;
  const series = history && history.length > 1 ? history : [lastPrice * 0.999, price];

  return (
    <Card className={cn("border-l-4", up ? "border-l-gain" : "border-l-loss")}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-sm font-medium">{name}</div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {inrPrecise(price).replace("₹", "")}
            </div>
          </div>
          <span className={cn("text-sm font-medium tabular-nums", signColor(change))}>
            {pct(change)}
          </span>
        </div>
        <div className="mt-2">
          <Sparkline data={series} color={color} />
        </div>
      </CardContent>
    </Card>
  );
}

export function MarketTab() {
  const state = useApi<MarketOverview>(() => api.marketOverview(), []);
  // Breadth at a glance — how many tracked indices are up vs down right now.
  const indices = state.data?.indices ?? [];
  const advancing = indices.filter((i) => i.change_pct >= 0).length;
  const stats: PageStat[] | undefined = state.data
    ? [
        { label: "Advancing", value: String(advancing), hint: `of ${indices.length}`, tone: "gain" },
        { label: "Declining", value: String(indices.length - advancing), tone: "loss" },
      ]
    : undefined;
  return (
    <div className="space-y-4">
      <PageHeader
        icon={BarChart3}
        title="Market"
        subtitle="Indices, your watchlist and the macro backdrop — live context for your book."
        stats={stats}
      />
      <Loadable state={state}>{(data) => <MarketGrid data={data} />}</Loadable>
      <WatchlistPanel />
      <MacroTab />
    </div>
  );
}

function MarketGrid({ data }: { data: MarketOverview }) {
  return (
    <div className="space-y-4">
      {data.is_fixture ? (
        <p className="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
          Showing fixture data (mock mode) — plausible placeholder values, not real
          market quotes. Portfolio-adjacent context only, not a screener.
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {data.indices.map((idx) => (
          <IndexCard
            key={idx.name}
            name={idx.name}
            lastPrice={idx.last_price}
            changePct={idx.change_pct}
          />
        ))}
      </div>
      <HoldingsMovers indexNames={data.indices.map((i) => i.name)} />
    </div>
  );
}

function MoverRow({ symbol }: { symbol: string }) {
  const tick = useTickerStore((s) => s.ticks[symbol]);
  const history = useTickerStore((s) => s.history[symbol]);
  if (!tick) return null;
  const up = tick.change_pct >= 0;
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="w-28 shrink-0 truncate text-sm font-medium">{symbol}</span>
      <div className="min-w-0 flex-1">
        <Sparkline
          data={history && history.length > 1 ? history : [tick.ltp, tick.ltp]}
          color={up ? CHART_GAIN : CHART_LOSS}
        />
      </div>
      <span className="w-24 shrink-0 text-right text-sm tabular-nums">
        {inrPrecise(tick.ltp).replace("₹", "")}
      </span>
      <span className={cn("w-16 shrink-0 text-right text-sm tabular-nums", signColor(tick.change_pct))}>
        {pct(tick.change_pct)}
      </span>
    </div>
  );
}

/** Live day movers across the user's own holdings, fed by the tick stream. */
function HoldingsMovers({ indexNames }: { indexNames: string[] }) {
  const symbols = useTickerStore(
    useShallow((s) => {
      const idx = new Set(indexNames);
      return Object.values(s.ticks)
        .filter((t) => !idx.has(t.symbol))
        .sort((a, b) => b.change_pct - a.change_pct)
        .map((t) => t.symbol);
    }),
  );
  if (symbols.length === 0) return null;
  return (
    <Panel
      title="Your Holdings Today"
      description="Live day change across your positions — biggest movers first."
    >
      <div className="divide-y divide-border">
        {symbols.map((sym) => (
          <MoverRow key={sym} symbol={sym} />
        ))}
      </div>
    </Panel>
  );
}
