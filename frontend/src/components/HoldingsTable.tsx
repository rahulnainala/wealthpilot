"use client";

import { memo } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SortHead, useSort } from "@/components/ui/sortable";
import { LivePrice, useLivePrice } from "@/components/LivePrice";
import { Tooltip } from "@/components/ui/tooltip";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { useTickerStore } from "@/store/useTickerStore";
import { bucketLabel } from "@/lib/buckets";
import { inr, inrPrecise, pct, signColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SnapshotHolding } from "@/lib/types";

/** Intraday volatility from the rolling tick history (stdev of returns). */
function useDayVol(symbol: string): number | null {
  return useTickerStore((s) => {
    const hist = s.history[symbol];
    if (!hist || hist.length < 6) return null;
    const rets = hist.slice(1).map((v, i) => (hist[i] > 0 ? v / hist[i] - 1 : 0));
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    const varsum = rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length;
    return Math.sqrt(varsum) * 100;
  });
}

function StockRow({ h, correlated }: { h: SnapshotHolding; correlated: Set<string> }) {
  const price = useLivePrice(h.symbol, h.last_price);
  const dayVol = useDayVol(h.symbol);
  const value = h.qty * price;
  const invested = h.qty * h.avg_price;
  const pnl = value - invested;
  const pnlPct = invested ? (pnl / invested) * 100 : 0;

  return (
    <TableRow>
      <TableCell className="font-medium">{h.symbol}</TableCell>
      <TableCell className="hidden text-right tabular-nums sm:table-cell">{h.qty}</TableCell>
      <TableCell className="hidden text-right tabular-nums text-muted-foreground lg:table-cell">
        {inrPrecise(h.avg_price)}
      </TableCell>
      <TableCell className="text-right">
        <LivePrice symbol={h.symbol} fallback={h.last_price} />
      </TableCell>
      <TableCell className="text-right tabular-nums">{inr(value)}</TableCell>
      <TableCell className={cn("text-right tabular-nums", signColor(pnl))}>
        {inr(pnl)}
        <span className="ml-1 hidden text-xs sm:inline">({pct(pnlPct)})</span>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge variant="outline">{bucketLabel(h.bucket)}</Badge>
      </TableCell>
      <TableCell className="hidden text-right lg:table-cell">
        <span className="inline-flex items-center justify-end gap-1.5">
          {correlated.has(h.symbol) ? (
            <Tooltip label="Highly correlated with another holding (≥0.6)" side="top">
              <span className="size-1.5 rounded-full bg-warning" />
            </Tooltip>
          ) : null}
          <span className="text-xs tabular-nums text-muted-foreground">
            {dayVol !== null ? `${dayVol.toFixed(2)}%` : "—"}
          </span>
        </span>
      </TableCell>
    </TableRow>
  );
}

export const HoldingsTable = memo(function HoldingsTable({
  holdings,
}: {
  holdings: SnapshotHolding[];
}) {
  const stocks = holdings.filter((h) => h.type === "stock");
  const div = useApi(() => api.diversification(), []);
  const correlated = new Set(
    (div.data?.top_pairs ?? [])
      .filter((p) => Math.abs(p.correlation) >= 0.6)
      .flatMap((p) => [p.label_a, p.label_b]),
  );
  const sort = useSort<SnapshotHolding>(
    stocks,
    {
      symbol: (h) => h.symbol,
      qty: (h) => h.qty,
      value: (h) => h.value,
      pnl: (h) => h.pnl,
      bucket: (h) => h.bucket,
    },
    "value",
  );

  if (stocks.length === 0) {
    return (
      <p className="px-5 py-4 text-sm text-muted-foreground">No direct holdings.</p>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <SortHead label="Symbol" sortKey="symbol" sort={sort} />
          <SortHead label="Qty" sortKey="qty" sort={sort} className="hidden text-right sm:table-cell" />
          <TableHead className="hidden text-right lg:table-cell">Avg</TableHead>
          <TableHead className="text-right">LTP</TableHead>
          <SortHead label="Value" sortKey="value" sort={sort} className="text-right" />
          <SortHead label="P&L" sortKey="pnl" sort={sort} className="text-right" />
          <SortHead label="Bucket" sortKey="bucket" sort={sort} className="hidden md:table-cell" />
          <TableHead className="hidden text-right lg:table-cell">
            <Tooltip label="Intraday volatility from live ticks · dot = concentration risk" side="top">
              <span>Risk</span>
            </Tooltip>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sort.sorted.map((h) => (
          <StockRow key={h.symbol} h={h} correlated={correlated} />
        ))}
      </TableBody>
    </Table>
  );
});
