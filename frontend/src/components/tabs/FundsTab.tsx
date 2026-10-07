"use client";

import { useState } from "react";
import { Landmark, Loader2 } from "lucide-react";

import { ProjectionChart } from "@/components/charts/ProjectionChart";
import { Loadable } from "@/components/Loadable";
import { PageHeader, type PageStat } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
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
import { dateOnly, inr, inrPrecise, pct, signColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Fund, MFAuditRow, MFOrder, ProjectionPoint } from "@/lib/types";

type Rec = Fund["recommendation"];

const REC_META: Record<Rec, { label: string; variant: "success" | "warning" | "info" }> = {
  keep: { label: "KEEP", variant: "info" },
  keep_grow: { label: "KEEP & GROW", variant: "success" },
  retire: { label: "RETIRE", variant: "warning" },
};

const REC_DOT: Record<Rec, string> = {
  keep: "bg-info",
  keep_grow: "bg-gain",
  retire: "bg-warning",
};

// ELSS is deliberately excluded from the audit (owner won't add to it —
// 2026-07-21): the two 80C funds are locked-in with no new money, so they're
// noise here. They still show honestly on the Basket tab as a held/paused
// sleeve, and the category prefix ("ELSS …") is the reliable tell.
const isElss = (category: string) => /elss/i.test(category);

function Stat({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("text-sm font-semibold tabular-nums", className)}>{value}</div>
    </div>
  );
}

function FundDetail({
  fund,
  auditRow,
  er,
  onErChange,
  onErCommit,
  saving,
}: {
  fund: Fund;
  /** Cost-audit metadata for this fund, if the backend has any on file. */
  auditRow: MFAuditRow | null;
  er: number;
  onErChange: (value: number) => void;
  onErCommit: (value: number) => void;
  saving: boolean;
}) {
  const orders = useApi<MFOrder[]>(() => api.fundOrders(fund.isin), [fund.isin]);
  const projection = useApi<ProjectionPoint[]>(
    () => api.fundProjection(fund.isin, 10),
    [fund.isin],
  );
  const rec = REC_META[fund.recommendation];
  const pnlPct = fund.invested ? (fund.pnl / fund.invested) * 100 : 0;
  const annualCost = (fund.value * er) / 100;

  return (
    <div className="space-y-4">
      <Panel
        title={fund.name}
        description={`${fund.category}${fund.goal_tag ? ` · ${fund.goal_tag}` : ""}`}
        action={<Badge variant={rec.variant}>{rec.label}</Badge>}
      >
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Value" value={inr(fund.value)} />
          <Stat label="Invested" value={inr(fund.invested)} />
          <Stat label="P&L" value={`${inr(fund.pnl)} (${pct(pnlPct)})`} className={signColor(fund.pnl)} />
          <Stat label="Units" value={fund.units.toString()} />
          <Stat label="NAV" value={inrPrecise(fund.nav)} />
          <Stat label="Avg NAV" value={inrPrecise(fund.avg_nav)} />
        </div>

        {/* Cost audit — folded in from the old MF Audit tab so a fund's cost
            lives next to its performance instead of on a separate page. */}
        <div className="mt-4 rounded-lg border border-border bg-muted/30 p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Cost &amp; audit
            </span>
            {saving ? (
              <span className="flex items-center gap-1 text-2xs text-muted-foreground">
                <Loader2 className="size-3 animate-spin" aria-hidden="true" /> saving…
              </span>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <div className="text-xs text-muted-foreground">Expense ratio</div>
              <div className="mt-1 flex items-center gap-1">
                <Input
                  type="number"
                  step="0.01"
                  min={0}
                  value={er}
                  onChange={(e) => onErChange(Number(e.target.value))}
                  onBlur={() => onErCommit(er)}
                  aria-label={`Expense ratio for ${fund.name}`}
                  className="h-7 w-16 text-right tabular-nums"
                />
                <span className="text-xs text-muted-foreground">%</span>
              </div>
            </div>
            <Stat label="Annual cost" value={inr(annualCost)} className="text-warning" />
            <div className="col-span-2">
              <div className="text-xs text-muted-foreground">Cheaper alternative</div>
              <div className="mt-1 text-sm font-medium">
                {auditRow?.alternative_name
                  ? `${auditRow.alternative_name} (${auditRow.alternative_er}%)`
                  : "None worth switching to"}
              </div>
            </div>
          </div>
          {auditRow?.rationale ? (
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{auditRow.rationale}</p>
          ) : null}
        </div>

        {fund.assigned_goals.length > 0 ? (
          <div className="mt-4 space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Feeds these goals</div>
            {fund.assigned_goals.map((g) => {
              const target = g.target_value ?? 0;
              const progress = target ? Math.min(100, (fund.value / target) * 100) : 0;
              const pending = Math.max(0, target - fund.value);
              return (
                <div key={g.key}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span>{g.name}</span>
                    <span className="text-muted-foreground tabular-nums">
                      {inr(fund.value)} of {inr(target)} · {inr(pending)} pending
                    </span>
                  </div>
                  <Progress value={progress} />
                </div>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">
            Not assigned to any goal yet — assign it in the Goals tab.
          </p>
        )}
      </Panel>

      <Panel
        title="10-year Growth Projection"
        description="Forward Monte Carlo of this fund's current value (C++ engine)."
        bodyClassName="h-64"
      >
        <Loadable state={projection}>
          {(points) => <ProjectionChart points={points} />}
        </Loadable>
      </Panel>

      <Panel title="Transactions" bodyClassName="p-0 sm:p-0">
        <Loadable state={orders} emptyMessage="No order history for this fund.">
          {(rows) =>
            rows.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">
                No orders returned. Kite&apos;s <code>mf_orders</code> API only surfaces
                recent or API-placed MF orders — your full Coin SIP history isn&apos;t
                exposed by the free Connect endpoints.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Units</TableHead>
                    <TableHead className="text-right">NAV</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((o) => (
                    <TableRow key={o.order_id}>
                      <TableCell>{dateOnly(o.order_timestamp)}</TableCell>
                      <TableCell>
                        <Badge variant={o.transaction_type === "BUY" ? "success" : "warning"}>
                          {o.transaction_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{o.quantity}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {inrPrecise(o.average_price)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{inr(o.amount)}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{o.status}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )
          }
        </Loadable>
      </Panel>
    </div>
  );
}

export function FundsTab() {
  const funds = useApi<Fund[]>(() => api.funds(), []);
  // The cost-audit metadata (ER, annual cost, alternatives) that used to be its
  // own MF Audit tab — joined by ISIN into each fund's detail below.
  const audit = useApi<MFAuditRow[]>(() => api.mfAudit(), []);
  const [selected, setSelected] = useState<string | null>(null);
  // Session ER overrides. Held at the tab level (not inside the detail) because
  // an edit changes the portfolio-wide cost total in the header too.
  const [ers, setErs] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);

  if (funds.loading || audit.loading) {
    // Mirrors the tab's shape (header, then fund list + detail), rounded-xl to
    // match the cards it becomes.
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 rounded-xl" />
        <div className="grid items-start gap-4 lg:grid-cols-[15rem_1fr]">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </div>
    );
  }
  if (funds.error || !funds.data) {
    return (
      <div className="px-4 py-8 text-center">
        <p className="mx-auto max-w-sm text-sm text-muted-foreground">
          No funds — refresh the portfolio first.
        </p>
      </div>
    );
  }

  const auditByIsin = new Map((audit.data ?? []).map((r) => [r.isin, r]));
  const effectiveEr = (isin: string) => ers[isin] ?? auditByIsin.get(isin)?.expense_ratio ?? 0;

  async function commitEr(isin: string, value: number) {
    // Persist the full ISIN→ER map (not just this fund) so the saved setting
    // stays a complete snapshot — same contract the backend audit reads back.
    const merged = { ...ers, [isin]: value };
    setErs(merged);
    setSaving(true);
    try {
      const full = Object.fromEntries(
        (audit.data ?? []).map((r) => [r.isin, merged[r.isin] ?? r.expense_ratio]),
      );
      await api.putSetting("expense_ratios", full);
      await audit.reload();
    } finally {
      setSaving(false);
    }
  }

  const hasElss = funds.data.some((f) => isElss(f.category));
  const visible = funds.data.filter((f) => !isElss(f.category));

  if (visible.length === 0) {
    return (
      <div className="px-4 py-8 text-center">
        <p className="mx-auto max-w-sm text-sm text-muted-foreground">
          No mutual funds to audit.
        </p>
      </div>
    );
  }

  const totalValue = visible.reduce((s, f) => s + f.value, 0);
  const totalAnnualCost = visible.reduce((s, f) => s + (f.value * effectiveEr(f.isin)) / 100, 0);
  const avgEr = totalValue ? (totalAnnualCost / totalValue) * 100 : 0;
  const retireCount = visible.filter((f) => f.recommendation === "retire").length;

  const activeIsin =
    selected && visible.some((f) => f.isin === selected) ? selected : visible[0].isin;
  const fund = visible.find((f) => f.isin === activeIsin) ?? visible[0];

  const stats: PageStat[] = [
    { label: "Funds", value: String(visible.length) },
    { label: "Value", value: inr(totalValue) },
    { label: "Cost / yr", value: inr(totalAnnualCost), tone: "warning", hint: `${avgEr.toFixed(2)}% avg` },
  ];
  if (retireCount > 0) {
    stats.push({ label: "To retire", value: String(retireCount), tone: "warning" });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Landmark}
        title="Funds"
        subtitle="Every mutual fund you hold — performance, goal fit and cost, audited in one place."
        stats={stats}
      />
      <div className="grid items-start gap-4 lg:grid-cols-[15rem_1fr]">
        <div className="flex flex-col gap-2">
          <div className="flex gap-1.5 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
            {visible.map((f) => {
              const p = f.invested ? (f.pnl / f.invested) * 100 : 0;
              return (
                <button
                  key={f.isin}
                  onClick={() => setSelected(f.isin)}
                  className={cn(
                    "min-w-52 shrink-0 rounded-lg border p-3 text-left transition-colors lg:min-w-0",
                    f.isin === fund.isin
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-muted",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{f.name}</span>
                    <span
                      className={cn("size-1.5 shrink-0 rounded-full", REC_DOT[f.recommendation])}
                      title={REC_META[f.recommendation].label}
                      aria-hidden="true"
                    />
                  </div>
                  <div className="mt-0.5 flex justify-between text-xs tabular-nums">
                    <span className="text-muted-foreground">{inr(f.value)}</span>
                    <span className={signColor(f.pnl)}>{pct(p)}</span>
                  </div>
                </button>
              );
            })}
          </div>
          {hasElss ? (
            <p className="px-1 text-2xs leading-relaxed text-muted-foreground">
              ELSS funds are excluded — locked-in (80C), no new money. They still show on the{" "}
              <a href="#basket" className="font-medium text-foreground underline underline-offset-2">
                Basket
              </a>{" "}
              tab.
            </p>
          ) : null}
        </div>
        <FundDetail
          key={fund.isin}
          fund={fund}
          auditRow={auditByIsin.get(fund.isin) ?? null}
          er={effectiveEr(fund.isin)}
          onErChange={(v) => setErs((prev) => ({ ...prev, [fund.isin]: v }))}
          onErCommit={(v) => void commitEr(fund.isin, v)}
          saving={saving}
        />
      </div>
    </div>
  );
}
