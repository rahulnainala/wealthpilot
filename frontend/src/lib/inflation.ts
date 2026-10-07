/**
 * Inflation shown across the Plan tabs.
 *
 * The owner's planning floor is 6% (2026-07-20) — long-run Indian CPI, with
 * healthcare and education running hotter. The backend clamps the FI
 * projection to the same floor (`MIN_INFLATION` in `app/services/ai/fi.py`);
 * this constant is the frontend half so Goals and Retirement can't drift.
 *
 * Note the two tabs run the conversion in opposite directions, deliberately:
 * Retirement's target is entered in *today's* money and inflated to the
 * nominal corpus that must be accumulated; Goals targets come from the Field
 * Plan already stated in *nominal* rupees at their target date, so they get
 * deflated to show what that will actually be worth.
 */
export const PLANNING_INFLATION = 0.06;

const MS_PER_YEAR = 365.25 * 24 * 3600 * 1000;

/** Years from now until `dateStr`, clamped at 0 for dates already passed. */
export function yearsFromNow(dateStr: string, now: Date = new Date()): number {
  return Math.max(0, (new Date(dateStr).getTime() - now.getTime()) / MS_PER_YEAR);
}

/**
 * What a future nominal amount is worth in today's purchasing power.
 * Returns null when there's no date to discount over — the caller should then
 * show nothing rather than a misleading equal-to-nominal figure.
 */
export function inTodaysMoney(
  nominal: number,
  targetDate: string | null,
  inflation: number = PLANNING_INFLATION,
  now: Date = new Date(),
): number | null {
  if (!targetDate) return null;
  const years = yearsFromNow(targetDate, now);
  if (years <= 0) return null;
  return nominal / (1 + inflation) ** years;
}
