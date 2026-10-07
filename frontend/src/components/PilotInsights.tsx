"use client";

import { useState } from "react";
import { AlertTriangle, Eye, Sparkles, X } from "lucide-react";

import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Per-severity presentation: action alerts shout, watch is amber, info is calm. */
const STYLES = {
  action: { icon: AlertTriangle, box: "border-loss/40 bg-loss/[0.08]", tint: "text-loss" },
  watch: { icon: Eye, box: "border-warning/40 bg-warning/[0.08]", tint: "text-warning" },
  info: { icon: Sparkles, box: "border-primary/25 bg-primary/[0.06]", tint: "text-primary" },
} as const;

/** Pilot speaks first: dismissible observations + Phase-7 rule-based watch alerts. */
export function PilotInsights() {
  const state = useApi(() => api.aiInsights(), []);
  const [hidden, setHidden] = useState<Set<number>>(new Set());

  const items = (state.data ?? []).filter((i) => !hidden.has(i.id));
  if (items.length === 0) return null;

  return (
    <div className="space-y-1.5">
      {items.map((i) => {
        const s = STYLES[(i.severity as keyof typeof STYLES)] ?? STYLES.info;
        const Icon = s.icon;
        return (
          <div
            key={i.id}
            className={cn(
              "flex items-center gap-2.5 rounded-lg border px-3.5 py-2 text-sm",
              s.box,
            )}
          >
            <Icon className={cn("size-3.5 shrink-0", s.tint)} aria-hidden="true" />
            <span className="min-w-0 flex-1">{i.text}</span>
            <button
              type="button"
              aria-label="Dismiss insight"
              onClick={() => {
                setHidden((h) => new Set(h).add(i.id));
                void api.aiDismissInsight(i.id).catch(() => {});
              }}
              className="flex size-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
