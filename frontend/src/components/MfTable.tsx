"use client";

import { memo } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { inr, inrPrecise, pct, signColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SnapshotHolding } from "@/lib/types";

export const MfTable = memo(function MfTable({
  holdings,
}: {
  holdings: SnapshotHolding[];
}) {
  const funds = holdings.filter((h) => h.type === "mf");
  if (funds.length === 0) {
    return (
      <p className="px-5 py-4 text-sm text-muted-foreground">
        No mutual fund holdings.
      </p>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Fund</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Units</TableHead>
          <TableHead className="hidden text-right md:table-cell">NAV</TableHead>
          <TableHead className="text-right">Value</TableHead>
          <TableHead className="text-right">P&amp;L</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {funds.map((h) => {
          const pnlPct = h.invested ? (h.pnl / h.invested) * 100 : 0;
          return (
            <TableRow key={h.symbol}>
              <TableCell className="max-w-[13rem] font-medium sm:max-w-[22rem]">
                <div className="truncate">{h.name ?? h.symbol}</div>
                <div className="text-xs text-muted-foreground">{h.symbol}</div>
              </TableCell>
              <TableCell className="hidden text-right tabular-nums sm:table-cell">{h.qty}</TableCell>
              <TableCell className="hidden text-right tabular-nums md:table-cell">
                {inrPrecise(h.last_price)}
              </TableCell>
              <TableCell className="text-right tabular-nums">{inr(h.value)}</TableCell>
              <TableCell className={cn("text-right tabular-nums", signColor(h.pnl))}>
                {inr(h.pnl)}
                <span className="ml-1 hidden text-xs sm:inline">({pct(pnlPct)})</span>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
});
