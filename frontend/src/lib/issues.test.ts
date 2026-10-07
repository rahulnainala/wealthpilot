import { describe, expect, it } from "vitest";

import {
  attentionIssues,
  countIssues,
  filterBySeverity,
  fixTabFor,
  issueKey,
} from "@/lib/issues";
import type { Issue, Severity } from "@/lib/types";

function issue(code: string, severity: Severity, symbols: string[] = []): Issue {
  return {
    code,
    severity,
    title: code,
    message: code,
    amount: null,
    pct_of_total: null,
    symbols,
  };
}

// A feed shaped like the real one: several rows sharing a code, mixed severity.
const FEED: Issue[] = [
  issue("dividend_overweight", "critical"),
  issue("psu_energy_cluster", "warning"),
  issue("single_symbol_concentration", "warning", ["ONGC"]),
  issue("single_symbol_concentration", "warning", ["INF789F01XA0"]),
  issue("position_too_small", "warning", ["HINDZINC"]),
  issue("position_drawdown", "info", ["HDFCGOLD"]),
  issue("gold_overweight", "info"),
];

describe("countIssues", () => {
  it("counts each severity", () => {
    const c = countIssues(FEED);
    expect(c.critical).toBe(1);
    expect(c.warning).toBe(4);
    expect(c.info).toBe(2);
    expect(c.total).toBe(7);
  });

  it("excludes info from `open` — info rows have no next step", () => {
    expect(countIssues(FEED).open).toBe(5);
  });

  it("open matches what the Overview band surfaces", () => {
    // The bug this pins: IssuesTab counted all severities while NeedsAttention
    // filtered info out, so the two disagreed about the same feed.
    expect(countIssues(FEED).open).toBe(attentionIssues(FEED).length);
  });

  it("handles an empty feed", () => {
    expect(countIssues([])).toEqual({
      critical: 0,
      warning: 0,
      info: 0,
      open: 0,
      total: 0,
    });
  });
});

describe("filterBySeverity", () => {
  it("passes the feed through for 'all'", () => {
    expect(filterBySeverity(FEED, "all")).toHaveLength(7);
  });

  it("filters to a single severity", () => {
    expect(filterBySeverity(FEED, "warning")).toHaveLength(4);
  });

  it("returns empty when nothing matches — the caller must render an empty state", () => {
    const noCriticals = FEED.filter((i) => i.severity !== "critical");
    expect(filterBySeverity(noCriticals, "critical")).toEqual([]);
  });
});

describe("attentionIssues", () => {
  it("drops info and puts criticals first", () => {
    const attn = attentionIssues(FEED);
    expect(attn.every((i) => i.severity !== "info")).toBe(true);
    expect(attn[0].severity).toBe("critical");
  });

  it("preserves backend order within a severity", () => {
    const attn = attentionIssues(FEED);
    expect(attn.slice(1).map((i) => i.code)).toEqual([
      "psu_energy_cluster",
      "single_symbol_concentration",
      "single_symbol_concentration",
      "position_too_small",
    ]);
  });

  it("does not mutate its input", () => {
    const feed = [...FEED];
    attentionIssues(feed);
    expect(feed.map((i) => i.code)).toEqual(FEED.map((i) => i.code));
  });
});

describe("issueKey", () => {
  it("is unique when rows share a code", () => {
    // Two concentration rows differ only by symbol; `code` alone collided.
    const dupes = FEED.filter((i) => i.code === "single_symbol_concentration");
    expect(dupes).toHaveLength(2);
    const keys = dupes.map((iss, i) => issueKey(iss, i));
    expect(new Set(keys).size).toBe(2);
  });

  it("produces one distinct key per row across a whole feed", () => {
    const keys = FEED.map(issueKey);
    expect(new Set(keys).size).toBe(FEED.length);
  });
});

describe("fixTabFor", () => {
  it.each([
    ["growth_missing_third", "basket"],
    ["dividend_overweight", "action-plan"],
    ["psu_energy_cluster", "action-plan"],
    ["single_symbol_concentration", "action-plan"],
    ["position_too_small", "action-plan"],
    ["duplicate_elss", "basket"],
    ["gold_overweight", "basket"],
    ["low_cash", "funds"],
  ])("routes %s to %s", (code, tab) => {
    expect(fixTabFor(code)).toBe(tab);
  });

  it("leaves position_drawdown unrouted — nothing here fixes a price move", () => {
    expect(fixTabFor("position_drawdown")).toBeNull();
  });

  it("returns null for an unknown code rather than guessing", () => {
    expect(fixTabFor("some_future_rule")).toBeNull();
  });

  it("matches on first hit, so narrower keys must precede broader ones", () => {
    // 'growth_missing_third' contains neither 'concentration' nor 'cluster',
    // but this ordering contract is what keeps that true as keys are added.
    expect(fixTabFor("GROWTH_MISSING_THIRD")).toBe("basket");
  });
});
