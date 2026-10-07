import { describe, expect, it } from "vitest";

import { sanePrice } from "./prices";

describe("sanePrice", () => {
  it("uses the tick when within band", () => {
    expect(sanePrice(100, 105)).toBe(105);
  });

  it("falls back to the reference when the tick diverges beyond band", () => {
    // Bad REIT feed: snapshot ₹340 vs stale Yahoo ₹263 (~22% off) -> keep 340.
    expect(sanePrice(340.1, 263.49)).toBe(340.1);
    expect(sanePrice(448.37, 369.92)).toBe(448.37);
  });

  it("falls back to the reference when there is no tick", () => {
    expect(sanePrice(100, undefined)).toBe(100);
  });

  it("uses the tick when the reference is non-positive", () => {
    expect(sanePrice(0, 50)).toBe(50);
  });
});
