"use client";

import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";

import { BacktestPanel } from "@/components/BacktestPanel";
import { BenchmarkPanel } from "@/components/BenchmarkPanel";
import { DiversificationPanel } from "@/components/DiversificationPanel";
import { FactorPanel } from "@/components/FactorPanel";
import { HedgePanel } from "@/components/HedgePanel";
import { OptimizePanel } from "@/components/OptimizePanel";
import { PageHeader, type PageStat } from "@/components/PageHeader";
import { RiskPanel } from "@/components/RiskPanel";
import { StressLabPanel } from "@/components/StressLabPanel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import type { PortfolioRisk } from "@/lib/types";

/** A labelled band of related risk panels — turns the flat 8-panel grid into an
 *  organised page with a clear reading order (exposure → optimisation →
 *  performance → stress). */
function RiskSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </h3>
      <div className="grid items-start gap-4 lg:grid-cols-2">{children}</div>
    </section>
  );
}

export function RiskTab() {
  // The engine's headline read, lifted to the page header so the tab answers
  // "how risky is the book?" before you scan the panels below.
  const risk = useApi<PortfolioRisk>(() => api.portfolioRisk(), []);
  const stats: PageStat[] | undefined = risk.data
    ? [
        { label: "1-day VaR", value: inr(risk.data.var), tone: "loss" },
        { label: "Volatility", value: `${(risk.data.annual_volatility * 100).toFixed(1)}%` },
        {
          label: "Max drawdown",
          value: `−${(risk.data.max_drawdown * 100).toFixed(1)}%`,
          tone: "loss",
        },
      ]
    : undefined;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={ShieldAlert}
        title="Risk"
        subtitle="Volatility, drawdown, diversification and stress — the engine's read on your book."
        stats={stats}
      />

      <RiskSection label="Exposure & diversification">
        <RiskPanel />
        <DiversificationPanel />
        <div className="lg:col-span-2">
          <FactorPanel />
        </div>
      </RiskSection>

      <RiskSection label="Optimization & hedging">
        <OptimizePanel />
        <HedgePanel />
      </RiskSection>

      <RiskSection label="Performance vs benchmark">
        <BenchmarkPanel />
        <BacktestPanel />
      </RiskSection>

      <RiskSection label="Stress testing">
        <div className="lg:col-span-2">
          <StressLabPanel />
        </div>
      </RiskSection>
    </div>
  );
}
