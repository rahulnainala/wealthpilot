/**
 * Trust a live tick only when it's within `band` of the reference (snapshot)
 * price. The Yahoo quote feed returns stale/wrong prices for some illiquid names
 * (e.g. REITs), which otherwise make the live total lurch away from the accurate
 * Kite snapshot. Out-of-band ticks fall back to the reference price.
 */
export function sanePrice(
  reference: number,
  tickLtp: number | undefined,
  band = 0.15,
): number {
  if (tickLtp == null) return reference;
  if (reference <= 0) return tickLtp;
  return Math.abs(tickLtp - reference) / reference > band ? reference : tickLtp;
}
