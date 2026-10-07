import { describe, expect, it } from "vitest";

import { dateOnly, inr, istTime, pct, sharePct, signColor } from "./format";

describe("format", () => {
  it("formats INR with Indian grouping and no decimals", () => {
    // 5,11,18.77 -> ₹51,119 (lakh grouping, rounded)
    expect(inr(4321987)).toBe("₹43,21,987");
    expect(inr(null)).toBe("—");
  });

  it("keeps small shares legible instead of rounding them to 0%", () => {
    // A long-dated goal is a fraction of a percent saved early on; showing a
    // flat "0%" reads as "nothing is happening" when the SIP is doing the work.
    expect(sharePct(0.319)).toBe("0.3%");
    expect(sharePct(0.04)).toBe("<0.1%");
    expect(sharePct(0)).toBe("0.0%");
    // Above 10% the decimal is noise.
    expect(sharePct(64.7)).toBe("65%");
    expect(sharePct(9.9)).toBe("9.9%");
    expect(sharePct(null)).toBe("—");
  });

  it("formats signed percentages", () => {
    expect(pct(3.117)).toBe("+3.12%");
    expect(pct(-8.4)).toBe("-8.40%");
    expect(pct(0)).toBe("0.00%");
    expect(pct(null)).toBe("—");
  });

  it("picks a color class by sign", () => {
    expect(signColor(5)).toContain("gain");
    expect(signColor(-5)).toContain("loss");
    expect(signColor(0)).toContain("muted");
  });

  it("does not sign a percentage that rounds away to zero", () => {
    // A -₹1 move on a small portfolio is -0.0018%, which rendered as "-0.00%"
    // and read as a loss. The rupee delta beside it carries the direction.
    expect(pct(-0.0018)).toBe("0.00%");
    expect(pct(0.0018)).toBe("0.00%");
    expect(pct(0)).toBe("0.00%");
    // Anything that survives rounding keeps its sign.
    expect(pct(-0.01)).toBe("-0.01%");
    expect(pct(0.01)).toBe("+0.01%");
  });

  it("renders timestamps in IST regardless of the browser's zone", () => {
    // 18:47 UTC is already the next calendar day in IST. Slicing the raw ISO
    // string (the previous approach) reported the UTC day, so a decision
    // logged just after IST midnight showed up dated a day earlier.
    const justAfterIstMidnight = "2026-07-19T18:47:07.654148+00:00";
    expect(dateOnly(justAfterIstMidnight)).toBe("20 Jul 2026");
    expect(istTime(justAfterIstMidnight)).toBe("00:17:07");
    // A date-only string parses as UTC midnight; IST keeps it on its own day.
    expect(dateOnly("2031-01-01")).toBe("1 Jan 2031");
    expect(dateOnly(null)).toBe("—");
  });
});
