"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Loadable } from "@/components/Loadable";
import { PageHeader, type PageStat } from "@/components/PageHeader";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import { severityAccent, severityVariant } from "@/lib/severity";
import {
  countIssues,
  filterBySeverity,
  fixTabFor,
  issueKey,
  type SeverityFilter,
} from "@/lib/issues";
import { AlertTriangle, ArrowRight } from "lucide-react";

import { AskAI } from "@/components/AskAI";
import { cn } from "@/lib/utils";
import type { Issue } from "@/lib/types";

function IssueRow({ issue }: { issue: Issue }) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border border-l-4 bg-card p-4 shadow-sm",
        severityAccent(issue.severity),
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge variant={severityVariant(issue.severity)}>{issue.severity}</Badge>
          <span className="font-medium">{issue.title}</span>
        </div>
        <span className="flex items-center gap-2">
          {issue.amount != null ? (
            <span className="text-sm font-medium tabular-nums">{inr(issue.amount)}</span>
          ) : null}
          <AskAI
            tip="Explain this issue"
            question={`Explain this portfolio issue and how to fix it: ${issue.title} — ${issue.message}`}
          />
          {fixTabFor(issue.code) ? (
            <a
              href={`#${fixTabFor(issue.code)}`}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              Fix <ArrowRight className="size-3" aria-hidden="true" />
            </a>
          ) : null}
        </span>
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">{issue.message}</p>
      {issue.symbols.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {issue.symbols.map((s) => (
            <Badge key={s} variant="outline">
              {s}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Chip({
  label,
  count,
  active,
  onClick,
  tone,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  tone?: string;
}) {
  return (
    <button
      onClick={onClick}
      // These are a filter toggle group, not navigation — without this the
      // selected filter is conveyed by colour alone to a screen reader.
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-transparent bg-primary text-primary-foreground"
          : "border-border hover:bg-muted",
      )}
    >
      <span className={cn("size-1.5 rounded-full", tone)} />
      {label}
      <span className="tabular-nums opacity-70">{count}</span>
    </button>
  );
}

function IssuesList({ issues }: { issues: Issue[] }) {
  const [filter, setFilter] = useState<SeverityFilter>("all");
  const counts = countIssues(issues);
  const shown = filterBySeverity(issues, filter);

  if (issues.length === 0) {
    return (
      <div className="px-4 py-8 text-center">
        <p className="mx-auto max-w-sm text-sm text-muted-foreground">No issues detected. 🎉</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Chip label="All" count={issues.length} active={filter === "all"} onClick={() => setFilter("all")} tone="bg-muted-foreground/50" />
        <Chip label="Critical" count={counts.critical} active={filter === "critical"} onClick={() => setFilter("critical")} tone="bg-loss" />
        <Chip label="Warning" count={counts.warning} active={filter === "warning"} onClick={() => setFilter("warning")} tone="bg-warning" />
        <Chip label="Info" count={counts.info} active={filter === "info"} onClick={() => setFilter("info")} tone="bg-info" />
      </div>
      {/* A severity filter that matches nothing used to render the chips over
          blank space — the empty guard above only covers an empty FEED, not an
          empty FILTER. Clicking "Critical" with zero criticals is the good news
          case, so say so rather than showing nothing. */}
      {shown.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">
          No {filter} issues. 🎉
        </p>
      ) : (
        shown.map((issue, i) => <IssueRow key={issueKey(issue, i)} issue={issue} />)
      )}
    </div>
  );
}

export function IssuesTab() {
  const state = useApi<Issue[]>(() => api.issues(), []);
  return (
    <Loadable state={state}>
      {(issues) => {
        const { critical, info, open } = countIssues(issues);
        // "Open" counts what you can act on. Info rows are ambient context —
        // gold sitting slightly over its band, a position down on the week —
        // and folding them into the headline inflated it (15 open, 3 of which
        // were nothing to do). NeedsAttention already excludes info; this makes
        // the two surfaces agree instead of quoting different totals.
        const stats: PageStat[] = [
          {
            label: "Open",
            value: String(open),
            tone: open === 0 ? "gain" : "warning",
          },
        ];
        if (critical > 0) {
          stats.push({ label: "Critical", value: String(critical), tone: "loss" });
        }
        if (info > 0) {
          stats.push({ label: "Info", value: String(info) });
        }
        return (
          <div className="space-y-4">
            <PageHeader
              icon={AlertTriangle}
              title="Issues"
              subtitle="Everything the audit flagged — each routed to where it gets fixed."
              stats={stats}
            />
            <IssuesList issues={issues} />
          </div>
        );
      }}
    </Loadable>
  );
}
