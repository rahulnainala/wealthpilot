"use client";

import { AlertTriangle, ArrowRight, CheckCircle2, ListChecks } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { attentionIssues, issueKey } from "@/lib/issues";
import type { ActionPlanItem, Issue } from "@/lib/types";

/**
 * The Overview's "needs attention" band — the one place the landing page answers
 * "does anything need me right now?". It consolidates the deterministic audit
 * findings (api.issues) and the rebalancing to-dos (api.actionPlan) that
 * otherwise live two nav groups away (Audit, Plan), and deep-links each row to
 * where it gets fixed. Full state set: a quiet placeholder while loading, a loud
 * tinted band when something's critical/pending, and a calm green "all clear"
 * line when nothing is — the happy path is designed, not left blank.
 */
export function NeedsAttention() {
  const issuesState = useApi<Issue[]>(() => api.issues(), []);
  const actionsState = useApi<ActionPlanItem[]>(() => api.actionPlan(), []);

  // Hold a quiet placeholder while either loads so the hero above doesn't jump
  // when the band resolves to its real height.
  if (issuesState.loading || actionsState.loading) {
    return (
      <div className="h-11 animate-pulse rounded-xl border border-border/60 bg-muted/30 motion-reduce:animate-none" />
    );
  }

  const actions = actionsState.data ?? [];
  // Info issues are ambient context, not something to act on — only critical and
  // warning earn a spot here, criticals first. Shared with the Issues tab's
  // "Open" count so the two surfaces cannot disagree about the same feed.
  const attn = attentionIssues(issuesState.data ?? []);

  // If issues couldn't load and there's nothing else to show, stay out of the
  // way rather than render a broken box — the Issues tab surfaces the error.
  if (issuesState.error && actions.length === 0) return null;

  if (attn.length === 0 && actions.length === 0) {
    // px-5 py-3 matches the sibling FlightStrip so the calm state carries the
    // same card rhythm as the loud one.
    return (
      <div className="flex items-center gap-2.5 rounded-xl border border-gain/30 bg-gain/[0.05] px-5 py-3 text-sm">
        <CheckCircle2 className="size-4 shrink-0 text-gain" aria-hidden="true" />
        <span className="font-medium">All clear</span>
        <span className="text-muted-foreground">
          — no open issues, nothing waiting in your action plan.
        </span>
      </div>
    );
  }

  const critical = attn.filter((i) => i.severity === "critical").length;
  const warning = attn.filter((i) => i.severity === "warning").length;
  const topAction = actions.slice().sort((a, b) => a.priority - b.priority)[0];

  return (
    <section
      aria-label="Needs attention"
      className={cn(
        "rounded-xl border shadow-sm",
        critical > 0
          ? "border-loss/40 bg-loss/[0.06]"
          : warning > 0
            ? "border-warning/40 bg-warning/[0.06]"
            : "border-primary/30 bg-primary/[0.05]",
      )}
    >
      {/* px-5 aligns the header's content edge with the hero / FlightStrip / panels
          stacked above and below it on the Overview column. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border/50 px-5 py-3">
        <AlertTriangle
          className={cn(
            "size-4 shrink-0",
            critical > 0 ? "text-loss" : warning > 0 ? "text-warning" : "text-primary",
          )}
          aria-hidden="true"
        />
        <span className="text-2xs font-semibold uppercase tracking-[0.14em]">
          Needs attention
        </span>
        <div className="flex items-center gap-1.5">
          {critical > 0 ? <Badge variant="critical">{critical} critical</Badge> : null}
          {warning > 0 ? <Badge variant="warning">{warning} warning</Badge> : null}
        </div>
        <a
          href="#issues"
          className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          Review all
          <ArrowRight className="size-3" aria-hidden="true" />
        </a>
      </div>

      <ul className="divide-y divide-border/40">
        {attn.slice(0, 2).map((issue, i) => (
          <li key={issueKey(issue, i)}>
            <a
              href="#issues"
              className="flex items-center gap-2.5 px-5 py-2 text-sm hover:bg-background/50"
            >
              {/* Severity is shown visually by the dot colour; give assistive
                  tech the same distinction in text rather than by colour alone. */}
              <span className="sr-only">
                {issue.severity === "critical" ? "Critical issue" : "Warning"}:{" "}
              </span>
              {/* The dot rides in a 14px slot (= the ListChecks glyph on the
                  action row) so every row's text column shares one left edge. */}
              <span className="flex w-3.5 shrink-0 justify-center" aria-hidden="true">
                <span
                  className={cn(
                    "size-1.5 rounded-full",
                    issue.severity === "critical" ? "bg-loss" : "bg-warning",
                  )}
                />
              </span>
              <span className="min-w-0 flex-1 truncate font-medium">{issue.title}</span>
              <span className="hidden shrink-0 truncate text-xs text-muted-foreground sm:block sm:max-w-[45%]">
                {issue.message}
              </span>
              <ArrowRight className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />
            </a>
          </li>
        ))}
        {attn.length > 2 ? (
          <li>
            <a
              href="#issues"
              className="block px-5 py-1.5 text-xs text-muted-foreground hover:text-foreground"
            >
              +{attn.length - 2} more open {attn.length - 2 === 1 ? "issue" : "issues"}
            </a>
          </li>
        ) : null}
        {topAction ? (
          <li>
            <a
              href="#action-plan"
              className="flex items-center gap-2.5 px-5 py-2 text-sm hover:bg-background/50"
            >
              <ListChecks className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">
                <span className="font-medium">Action plan</span>
                <span className="text-muted-foreground"> · {topAction.title}</span>
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {actions.length} {actions.length === 1 ? "step" : "steps"}
              </span>
              <ArrowRight className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />
            </a>
          </li>
        ) : null}
      </ul>
    </section>
  );
}
