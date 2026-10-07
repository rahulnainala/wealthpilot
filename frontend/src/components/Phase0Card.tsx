"use client";

import { useEffect, useState } from "react";
import { Check, ChevronRight, ShieldCheck } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

const ITEMS = [
  { key: "debt", label: "Clear high-interest debt" },
  { key: "emergency", label: "6-month emergency fund" },
  { key: "insurance", label: "Health insurance" },
] as const;

type Phase0 = { debt: boolean; emergency: boolean; insurance: boolean };
const DEFAULT: Phase0 = { debt: false, emergency: false, insurance: false };

export function Phase0Card() {
  const [state, setState] = useState<Phase0>(DEFAULT);
  const [loaded, setLoaded] = useState(false);
  // Once the gate is cleared it doesn't need a full banner every visit — it
  // collapses to a one-line confirmation, re-expandable to un-check an item.
  const [reviewing, setReviewing] = useState(false);

  useEffect(() => {
    api
      .getSetting("phase0")
      .then((s) => setState({ ...DEFAULT, ...(s.value as Partial<Phase0>) }))
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 404)) console.error(e);
      })
      .finally(() => setLoaded(true));
  }, []);

  const done = ITEMS.filter((i) => state[i.key]).length;
  const complete = done === ITEMS.length;

  async function toggle(key: keyof Phase0) {
    const next = { ...state, [key]: !state[key] };
    setState(next);
    try {
      await api.putSetting("phase0", next);
    } catch {
      setState(state); // revert on failure
    }
  }

  // Cleared and not being reviewed: a slim confirmation strip instead of the
  // full three-button banner, matching the Overview's "all clear" rhythm.
  if (complete && !reviewing) {
    return (
      <div className="flex items-center gap-2.5 rounded-xl border border-gain/30 bg-gain/[0.05] px-5 py-2.5 text-sm">
        <ShieldCheck className="size-4 shrink-0 text-gain" aria-hidden="true" />
        <span className="font-medium">Phase 0 foundation complete</span>
        <span className="hidden text-muted-foreground sm:inline">
          — cleared to run your bucket SIPs.
        </span>
        <button
          type="button"
          onClick={() => setReviewing(true)}
          className="ml-auto inline-flex items-center gap-0.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          Review
          <ChevronRight className="size-3" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-xl border p-5 shadow-sm",
        complete
          ? "border-gain/30 bg-gain/[0.06]"
          : "border-warning/30 bg-warning/[0.06]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div
            className={cn(
              "flex size-9 shrink-0 items-center justify-center rounded-lg",
              complete
                ? "bg-gain/15 text-gain"
                : "bg-warning/15 text-warning",
            )}
          >
            <ShieldCheck className="size-[18px]" />
          </div>
          <div>
            <h3 className="font-semibold leading-tight">Phase 0 — foundation first</h3>
            <p className="text-xs text-muted-foreground">
              {complete
                ? "Complete — cleared to start your bucket SIPs."
                : "Buckets stay empty until this is done — by design."}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-sm font-semibold tabular-nums text-muted-foreground">
            {done}/{ITEMS.length}
          </span>
          {complete ? (
            <button
              type="button"
              onClick={() => setReviewing(false)}
              className="text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              Hide
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-3 grid gap-1.5 sm:grid-cols-3">
        {ITEMS.map((i) => {
          const on = state[i.key];
          return (
            <button
              key={i.key}
              onClick={() => toggle(i.key)}
              disabled={!loaded}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors disabled:opacity-60",
                on
                  ? "border-gain/40 bg-gain/10"
                  : "border-border hover:bg-muted",
              )}
            >
              <span
                className={cn(
                  "flex size-4 shrink-0 items-center justify-center rounded-full border",
                  on
                    ? "border-gain bg-gain text-primary-foreground"
                    : "border-muted-foreground/40",
                )}
              >
                {on ? <Check className="size-3" /> : null}
              </span>
              {i.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
