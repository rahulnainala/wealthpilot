import { inr } from "@/lib/format";

/** Visualizes the p10–p90 ending-value band with median and target markers. */
export function SimRangeBar({
  p10,
  p90,
  median,
  target,
}: {
  p10: number;
  p90: number;
  median: number;
  target: number;
}) {
  const lo = Math.min(p10, median, target);
  const hi = Math.max(p90, median, target);
  const span = hi - lo || 1;
  const posOf = (v: number) => ((v - lo) / span) * 100;

  return (
    <div>
      <div className="relative h-3 w-full rounded-full bg-muted">
        <div
          className="absolute top-0 h-3 rounded-full bg-primary/25"
          style={{ left: `${posOf(p10)}%`, width: `${posOf(p90) - posOf(p10)}%` }}
        />
        <div
          className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-primary"
          style={{ left: `${posOf(median)}%` }}
          title={`Median ${inr(median)}`}
        />
        <div
          className="absolute top-[-2px] h-[16px] w-0.5 bg-loss"
          style={{ left: `${posOf(target)}%` }}
          title={`Target ${inr(target)}`}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-muted-foreground tabular-nums">
        <span>p10 {inr(p10)}</span>
        <span className="text-loss">target {inr(target)}</span>
        <span>p90 {inr(p90)}</span>
      </div>
    </div>
  );
}
