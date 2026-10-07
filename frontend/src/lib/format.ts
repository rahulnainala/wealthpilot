const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const inrPreciseFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** ₹ with Indian digit grouping (lakh/crore), no decimals. */
export function inr(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return inrFormatter.format(value);
}

/** ₹ with two decimals (for prices/NAVs). */
export function inrPrecise(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return inrPreciseFormatter.format(value);
}

/** Signed percentage, e.g. "+3.12%". */
export function pct(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  // A change too small to survive rounding renders unsigned: "-0.00%" reads as
  // a loss at a glance when the figure is flat, and the rupee delta alongside
  // already carries the direction.
  const rounded = Number(value.toFixed(digits));
  if (rounded === 0) return `${(0).toFixed(digits)}%`;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

/**
 * IST calendar date of a timestamp as a sortable `YYYY-MM-DD` key.
 *
 * The frontend mirror of the backend's `ist_date()` — snapshots are stamped in
 * UTC, and the browser's local zone must never decide which trading day a row
 * belongs to. `en-CA` is the shortest route to ISO-ordered output, so plain
 * string comparison is also chronological comparison.
 */
const IST_DATE_FMT = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function istDateKey(ts: string | Date): string {
  return IST_DATE_FMT.format(typeof ts === "string" ? new Date(ts) : ts);
}

/**
 * Unsigned share, kept legible at the small end.
 *
 * Early in a long-dated goal the saved-vs-target share is a fraction of a
 * percent — rounding that to a flat "0%" reads as "nothing is happening" when
 * the SIP is doing the work, so sub-10% values keep a decimal and anything
 * genuinely non-zero never renders as 0%.
 */
export function sharePct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value > 0 && value < 0.1) return "<0.1%";
  return `${value < 10 ? value.toFixed(1) : value.toFixed(0)}%`;
}

/** Tailwind text color class by sign (green up / red down / muted flat). */
export function signColor(value: number): string {
  if (value > 0) return "text-gain";
  if (value < 0) return "text-loss";
  return "text-muted-foreground";
}

/** "6 Jul 2026, 09:45" from an ISO string. */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "6 Jul 2026" from an ISO date string. */
/**
 * A timestamp as an IST calendar date.
 *
 * The zone is pinned rather than left to the browser: every record here is an
 * Indian financial one, and the owner may be abroad before these goals
 * mature — a browser in another zone would otherwise re-date IST-stamped rows.
 * It also fixes date-only strings ("2031-01-01"), which parse as UTC midnight
 * and slip a day back in any zone behind UTC.
 */
export function dateOnly(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Clock time of a timestamp in IST (HH:MM:SS) — the market's own zone. */
export function istTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-GB", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
