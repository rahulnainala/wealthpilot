/**
 * Pure helpers for the issue feed.
 *
 * These were inline in IssuesTab and NeedsAttention, where nothing could reach
 * them — and that is exactly where the bugs lived: an "Open" count that
 * disagreed between two components rendering the same feed, a React key built
 * from a non-unique field, and a filter whose empty case fell through to blank
 * space. None of it needs React, so none of it should require rendering React
 * to verify.
 */
import type { Issue, Severity } from "@/lib/types";

export type SeverityFilter = Severity | "all";

/** Severity ordering used everywhere issues are ranked. */
export const SEVERITY_RANK: Record<Severity, number> = {
  critical: 0,
  warning: 1,
  info: 2,
};

export interface IssueCounts {
  critical: number;
  warning: number;
  info: number;
  /** Rows you can act on: critical + warning. */
  open: number;
  /** Every row in the feed, info included. */
  total: number;
}

/**
 * Count a feed by severity.
 *
 * `open` deliberately excludes info. Info rows are ambient context — gold a
 * little over its band, a position down on the week — and counting them as
 * "open issues" inflates the headline with things that have no next step. Both
 * surfaces read `open` from here so they can no longer disagree about how many
 * problems the same feed contains.
 */
export function countIssues(issues: Issue[]): IssueCounts {
  const critical = issues.filter((i) => i.severity === "critical").length;
  const warning = issues.filter((i) => i.severity === "warning").length;
  const info = issues.filter((i) => i.severity === "info").length;
  return { critical, warning, info, open: critical + warning, total: issues.length };
}

/** Apply a severity chip filter. `"all"` passes the feed through untouched. */
export function filterBySeverity(issues: Issue[], filter: SeverityFilter): Issue[] {
  return filter === "all" ? issues : issues.filter((i) => i.severity === filter);
}

/**
 * The rows the Overview band should surface: actionable only, most severe
 * first, original order preserved within a severity (the backend already emits
 * a meaningful order inside each level).
 */
export function attentionIssues(issues: Issue[]): Issue[] {
  return issues
    .filter((i) => i.severity !== "info")
    .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
}

/**
 * A stable React key.
 *
 * `code` alone is NOT unique: single_symbol_concentration and
 * position_too_small emit one issue per offending symbol, so a feed routinely
 * carries several rows sharing a code.
 */
export function issueKey(issue: Issue, index: number): string {
  return `${issue.code}-${index}`;
}

/**
 * Route each issue class to the surface where it gets fixed.
 *
 * Order matters: `fixTabFor` takes the FIRST substring hit, so narrower keys
 * must sit above broader ones.
 */
export const FIX_TAB: Record<string, string> = {
  concentration: "action-plan",
  cluster: "action-plan",
  // Both resolve through the legacy sell-off: the dividend bucket is overweight
  // *because* the PSU/REIT basket is still being wound down.
  dividend: "action-plan",
  too_small: "action-plan",
  // Growth is short because new SIP routing decides it, not a sale.
  growth: "basket",
  allocation: "basket",
  bucket: "basket",
  cash: "funds",
  // MF Audit merged into Funds; the cost audit lives there now.
  mf: "funds",
  expense: "funds",
  // ELSS is filtered out of the Funds audit — the duplicate is redeemed and its
  // proceeds redirected to Growth, which is a Basket (SIP-routing) action.
  elss: "basket",
  gold: "basket",
};

/**
 * The tab that fixes this issue, or `null` when there isn't one.
 *
 * `position_drawdown` is intentionally unmapped: a position being down is the
 * market moving, and no screen in this app "fixes" a price.
 */
export function fixTabFor(code: string): string | null {
  const c = code.toLowerCase();
  for (const key of Object.keys(FIX_TAB)) {
    if (c.includes(key)) return FIX_TAB[key];
  }
  return null;
}
