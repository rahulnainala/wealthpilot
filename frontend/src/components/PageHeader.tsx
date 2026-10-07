import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Shared page header used across tabs (Goals, Retirement, Basket, Action
 * Plan). Before this, every Plan tab dived straight into content with no title
 * and four different top-of-page treatments — this gives the section one
 * consistent, oriented header: a tinted icon, a title + one-line context, and
 * an optional row of at-a-glance stats pulled from that page's own data.
 *
 * It renders an <h2> on purpose: the app name in the sticky Dashboard header is
 * the page <h1>, so each tab's title sits one level below it.
 */
type StatTone = "gain" | "loss" | "warning" | "primary" | "default";

const TONE_CLASS: Record<StatTone, string> = {
  gain: "text-gain",
  loss: "text-loss",
  warning: "text-warning",
  primary: "text-primary",
  default: "text-foreground",
};

export interface PageStat {
  label: string;
  value: React.ReactNode;
  tone?: StatTone;
  /** Optional muted suffix on the same line as the value (e.g. "of 3"). */
  hint?: string;
}

interface Props {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  stats?: PageStat[];
  /** Optional trailing controls (a link/button), shown after the stats. */
  action?: React.ReactNode;
  className?: string;
}

export function PageHeader({ icon: Icon, title, subtitle, stats, action, className }: Props) {
  const hasStats = stats && stats.length > 0;
  return (
    <header
      className={cn(
        "flex flex-col gap-4 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-inset ring-primary/20">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h2 className="text-lg font-bold leading-tight tracking-tight">{title}</h2>
          {subtitle ? (
            <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
      </div>

      {hasStats || action ? (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 sm:justify-end">
          {hasStats ? (
            <dl className="flex flex-wrap items-center gap-x-6 gap-y-3">
              {stats!.map((s) => (
                <div key={s.label} className="min-w-0">
                  <dt className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    {s.label}
                  </dt>
                  <dd
                    className={cn(
                      "mt-1 text-lg font-semibold leading-none tabular-nums",
                      TONE_CLASS[s.tone ?? "default"],
                    )}
                  >
                    {s.value}
                    {s.hint ? (
                      <span className="ml-1 text-xs font-normal text-muted-foreground">
                        {s.hint}
                      </span>
                    ) : null}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
          {action}
        </div>
      ) : null}
    </header>
  );
}
