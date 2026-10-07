import { describe, expect, it } from "vitest";

import {
  buildExitItem,
  exitStatus,
  isSellNow,
  monthsLeftLabel,
  monthsRemaining,
  routeProceeds,
  sortExitItems,
  windowElapsedPct,
  WINDOW_END,
  WINDOW_START,
} from "./exitPlan";
import type { SnapshotHolding } from "./types";

// Fixture dates are DERIVED from WINDOW_END, never typed as literals. They
// used to be absolute ("2027-11-01"), which only meant "near the deadline"
// while the deadline was Dec 2027 — moving it to Jun 2027 silently turned
// "6 months out" into "already past". Same class of bug the WINDOW_END_LABEL
// change fixes in the UI.
const MS_PER_MONTH = 1000 * 60 * 60 * 24 * 30.44;
const monthsBeforeEnd = (n: number) => new Date(WINDOW_END.getTime() - n * MS_PER_MONTH);

const MID_WINDOW = monthsBeforeEnd(9);
const NEAR_DEADLINE = monthsBeforeEnd(1);

function holding(overrides: Partial<SnapshotHolding> = {}): SnapshotHolding {
  return {
    symbol: "ONGC",
    name: "ONGC",
    type: "stock",
    bucket: "dividend",
    qty: 10,
    avg_price: 100,
    last_price: 100,
    value: 1000,
    invested: 1000,
    pnl: 0,
    ...overrides,
  } as SnapshotHolding;
}

describe("exitStatus", () => {
  it("is ready at or above the +10% threshold", () => {
    expect(exitStatus(10, MID_WINDOW)).toBe("ready");
    expect(exitStatus(23.4, MID_WINDOW)).toBe("ready");
  });

  it("is near between +7% and +10% mid-window", () => {
    expect(exitStatus(7, MID_WINDOW)).toBe("near");
    expect(exitStatus(9.9, MID_WINDOW)).toBe("near");
  });

  it("is hold below +7% mid-window", () => {
    expect(exitStatus(0, MID_WINDOW)).toBe("hold");
    expect(exitStatus(-8, MID_WINDOW)).toBe("hold");
  });

  it("flags deadline for unsold positions near the window end", () => {
    expect(exitStatus(2, NEAR_DEADLINE)).toBe("deadline");
    expect(exitStatus(-5, NEAR_DEADLINE)).toBe("deadline");
  });

  it("ready still wins over deadline near the window end", () => {
    expect(exitStatus(12, NEAR_DEADLINE)).toBe("ready");
  });
});

describe("buildExitItem", () => {
  it("computes P&L from the live price, not the snapshot value", () => {
    const item = buildExitItem(holding(), 112, MID_WINDOW);
    expect(item.value).toBe(1120);
    expect(item.pnl).toBe(120);
    expect(item.pnlPct).toBeCloseTo(12);
    expect(item.status).toBe("ready");
    expect(item.progressPct).toBe(100);
  });

  it("clamps threshold progress for losing positions", () => {
    const item = buildExitItem(holding(), 90, MID_WINDOW);
    expect(item.pnlPct).toBeCloseTo(-10);
    expect(item.progressPct).toBe(0);
    expect(item.status).toBe("hold");
  });
});

describe("sortExitItems", () => {
  it("orders ready → deadline → near → hold, then by P&L%", () => {
    const mk = (symbol: string, price: number, now: Date) =>
      buildExitItem(holding({ symbol }), price, now);
    const items = [
      mk("HOLD", 101, MID_WINDOW),
      mk("READY-LOW", 111, MID_WINDOW),
      mk("NEAR", 108, MID_WINDOW),
      mk("READY-HIGH", 120, MID_WINDOW),
    ];
    expect(sortExitItems(items).map((i) => i.symbol)).toEqual([
      "READY-HIGH",
      "READY-LOW",
      "NEAR",
      "HOLD",
    ]);
  });
});

describe("routeProceeds", () => {
  it("splits 50/30/20 and fund shares sum back to the amount", () => {
    const routes = routeProceeds(100000);
    expect(routes.map((r) => r.amount)).toEqual([50000, 30000, 20000]);
    const fundTotal = routes.flatMap((r) => r.funds).reduce((s, f) => s + f.amount, 0);
    expect(fundTotal).toBeCloseTo(100000);
    expect(routes[0].funds[0]).toEqual({ name: "UTI Nifty 50 Index", amount: 30000 });
  });
});

describe("window math", () => {
  it("counts down and clamps at the deadline", () => {
    expect(monthsRemaining(MID_WINDOW)).toBeCloseTo(9, 1);
    expect(monthsRemaining(new Date(WINDOW_END.getTime() + 1))).toBe(0);
    expect(windowElapsedPct(WINDOW_START)).toBe(0);
    expect(windowElapsedPct(new Date(WINDOW_END.getTime() + MS_PER_MONTH))).toBe(100);
  });

  it("treats deadline positions as sell-now alongside ready ones", () => {
    // Past the urgency cutoff a position exits regardless of P&L. Counting
    // only "ready" would report nothing to sell on exactly the run where
    // everything has to go.
    expect(isSellNow("ready")).toBe(true);
    expect(isSellNow("deadline")).toBe(true);
    expect(isSellNow("near")).toBe(false);
    expect(isSellNow("hold")).toBe(false);
  });

  it("gives one whole-month answer for the window, shared across tabs", () => {
    // Action Plan used ceil and Basket used round, so the same deadline read
    // as "18mo" on one tab and "17mo" on the other.
    expect(monthsLeftLabel(monthsBeforeEnd(6))).toBe(6);
    expect(monthsLeftLabel(new Date(WINDOW_END.getTime() + MS_PER_MONTH))).toBe(0);
  });
});
