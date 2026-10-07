"use client";

import { useEffect, useState } from "react";
import { RefreshCw, ShieldQuestion } from "lucide-react";

import { Panel } from "@/components/Panel";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const DOT: Record<string, string> = {
  action: "bg-loss",
  watch: "bg-warning",
  info: "bg-primary",
};

/** Phase 28: the nightly action agent's ranked "do this today" plan. */
export function DailyPlanPanel() {
  const state = useApi(() => api.aiDailyPlan(), []);
  const [items, setItems] = useState<{ severity: string; title: string }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [critique, setCritique] = useState<string | null>(null);
  const [critiquing, setCritiquing] = useState(false);
  const [auto, setAuto] = useState<boolean | null>(null);

  useEffect(() => {
    api.autoExecuteStatus().then((r) => setAuto(r.enabled)).catch(() => setAuto(null));
  }, []);

  async function toggleAuto() {
    if (auto === null) return;
    const next = !auto;
    if (next && !window.confirm("Enable AUTONOMOUS order placement? Pilot will place real GTT sells when a stock crosses +10%, without asking each time. Only active in secured mode.")) return;
    try {
      const r = await api.setAutoExecute(next);
      setAuto(r.enabled);
    } catch {
      /* ignore */
    }
  }

  const plan = items ?? state.data?.items ?? [];

  async function rebuild() {
    setBusy(true);
    try {
      setItems((await api.aiRefreshDailyPlan()).items);
      setCritique(null);
    } finally {
      setBusy(false);
    }
  }

  async function devilsAdvocate() {
    setCritiquing(true);
    try {
      setCritique((await api.aiCritique()).critique ?? "The 3070 is offline — no critique available.");
    } finally {
      setCritiquing(false);
    }
  }

  return (
    <Panel
      title="Today's Plan"
      description="Pilot's ranked to-do — watch, optimize, and tax in one list."
      action={
        <Button variant="outline" size="sm" onClick={() => void rebuild()} disabled={busy}>
          <RefreshCw aria-hidden="true" />
          <span className="hidden sm:inline">Rebuild</span>
        </Button>
      }
    >
      {plan.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {busy ? "Building your plan…" : "No actions right now — you're on track."}
        </p>
      ) : (
        <ol className="space-y-2">
          {plan.map((it, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm">
              <span className="mt-0.5 text-xs font-semibold tabular-nums text-muted-foreground">
                {i + 1}
              </span>
              <span
                className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", DOT[it.severity] ?? "bg-muted-foreground")}
                aria-hidden="true"
              />
              <span>{it.title}</span>
            </li>
          ))}
        </ol>
      )}
      {plan.length > 0 ? (
        <div className="mt-4 border-t border-border pt-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void devilsAdvocate()}
            disabled={critiquing}
            className="text-xs text-muted-foreground"
          >
            <ShieldQuestion aria-hidden="true" />
            {critiquing ? "Stress-testing…" : "Devil's advocate"}
          </Button>
          {critique ? (
            <p className="mt-1 whitespace-pre-wrap rounded-lg border border-warning/30 bg-warning/[0.06] p-2.5 text-xs text-muted-foreground">
              {critique}
            </p>
          ) : null}
        </div>
      ) : null}
      {auto !== null ? (
        <label className="mt-3 flex items-center gap-2 border-t border-border pt-3 text-xs">
          <input type="checkbox" checked={auto} onChange={() => void toggleAuto()} className="accent-[var(--loss)]" />
          <span className={auto ? "font-semibold text-loss" : "text-muted-foreground"}>
            Auto-execute +10% sells {auto ? "ON" : "off"}
          </span>
          <span className="text-2xs text-muted-foreground">
            — autonomous real orders (secured mode only). Off by default.
          </span>
        </label>
      ) : null}
    </Panel>
  );
}
