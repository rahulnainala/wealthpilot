"use client";

import { Briefcase } from "lucide-react";

import { HoldingsTable } from "@/components/HoldingsTable";
import { MfTable } from "@/components/MfTable";
import { NetWorthPanel } from "@/components/NetWorthPanel";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { XrayPanel } from "@/components/XrayPanel";
import { inr } from "@/lib/format";
import type { Snapshot } from "@/lib/types";

export function HoldingsTab({ snapshot }: { snapshot: Snapshot }) {
  const stocks = snapshot.holdings.filter((h) => h.type === "stock");
  const funds = snapshot.holdings.filter((h) => h.type === "mf");
  const stocksValue = stocks.reduce((sum, h) => sum + h.value, 0);
  const fundsValue = funds.reduce((sum, h) => sum + h.value, 0);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Briefcase}
        title="Holdings"
        subtitle="Every position you hold — stocks, funds and the net-worth picture."
        stats={[
          { label: "Positions", value: String(snapshot.holdings.length) },
          { label: "Stocks", value: inr(stocksValue) },
          { label: "Funds", value: inr(fundsValue), tone: "primary" },
        ]}
      />
      <Panel title="Holdings" bodyClassName="p-0 sm:p-0">
        <HoldingsTable holdings={snapshot.holdings} />
      </Panel>
      <Panel title="Mutual Funds" bodyClassName="p-0 sm:p-0">
        <MfTable holdings={snapshot.holdings} />
      </Panel>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <XrayPanel />
        <NetWorthPanel />
      </div>
    </div>
  );
}
