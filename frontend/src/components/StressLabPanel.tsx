"use client";

import { useState } from "react";

import { Panel } from "@/components/Panel";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import { cn } from "@/lib/utils";

const SCENARIOS = [
  { key: "energy", label: "Crude shock" },
  { key: "market", label: "Market crash" },
  { key: "rates", label: "Rate spike" },
  { key: "gold", label: "Gold rally" },
];

/** Phase 32: sector-aware stress scenarios on the portfolio. */
export function StressLabPanel() {
  const [res, setRes] = useState<Awaited<ReturnType<typeof api.aiStress>> | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(scenario: string) {
    setActive(scenario);
    setBusy(true);
    try {
      setRes(await api.aiStress(scenario));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Stress lab" description="Sector-aware shocks — energy hits harder than gold.">
      <div className="flex flex-wrap gap-2">
        {SCENARIOS.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => void run(s.key)}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs",
              active === s.key ? "border-primary bg-primary/10 text-foreground" : "border-input hover:bg-muted",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>
      {busy ? (
        <p className="mt-3 text-sm text-muted-foreground">Shocking the book…</p>
      ) : res ? (
        <div className="mt-3 space-y-2">
          <div className="flex items-baseline gap-3">
            <span className="text-sm text-muted-foreground">{res.label}</span>
            <span
              className={cn(
                "text-2xl font-semibold tabular-nums",
                res.change_pct >= 0 ? "text-gain" : "text-loss",
              )}
            >
              {res.change_pct >= 0 ? "+" : ""}
              {res.change_pct.toFixed(1)}%
            </span>
            <span className="ml-auto text-xs tabular-nums text-muted-foreground">
              {inr(res.total_before)} → {inr(res.total_after)}
            </span>
          </div>
          <ul className="space-y-1">
            {res.top_hits.map((h) => (
              <li key={h.symbol} className="flex justify-between text-xs tabular-nums text-muted-foreground">
                <span>
                  {h.symbol} <span className="opacity-70">({h.shock}%)</span>
                </span>
                <span className={h.change >= 0 ? "text-gain" : "text-loss"}>{inr(h.change)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Pick a scenario to shock the portfolio.</p>
      )}
    </Panel>
  );
}
