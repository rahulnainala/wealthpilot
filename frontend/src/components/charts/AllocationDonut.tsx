"use client";

import { memo } from "react";
import { Doughnut } from "react-chartjs-2";

import { ensureChartsRegistered } from "@/components/charts/chartSetup";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { BUCKETS, bucketColor } from "@/lib/buckets";
import { inr } from "@/lib/format";

ensureChartsRegistered();

const ORDER = ["growth", "dividend", "mf", "other", "cash"];

interface Props {
  bucketValues: Record<string, number>;
  cash: number;
  /** Hide the chart's built-in legend when the caller renders its own. */
  showLegend?: boolean;
}

export const AllocationDonut = memo(function AllocationDonut({
  bucketValues,
  cash,
  showLegend = true,
}: Props) {
  // The right-hand legend starves the donut of width on phones; stack it below.
  const narrow = useMediaQuery("(max-width: 639px)");

  const values: Record<string, number> = { ...bucketValues, cash };
  const present = ORDER.filter((k) => (values[k] ?? 0) > 0);
  const total = present.reduce((sum, k) => sum + (values[k] ?? 0), 0);

  const summary = present
    .map(
      (k) =>
        `${BUCKETS[k].label} ${total > 0 ? (((values[k] ?? 0) / total) * 100).toFixed(0) : 0}%`,
    )
    .join(", ");

  return (
    <Doughnut
      role="img"
      aria-label={`Current allocation donut chart: ${summary}`}
      data={{
        labels: present.map((k) => BUCKETS[k].label),
        datasets: [
          {
            data: present.map((k) => Number((values[k] ?? 0).toFixed(2))),
            backgroundColor: present.map((k) => bucketColor(k)),
            borderWidth: 2,
            borderColor: "transparent",
            hoverOffset: 6,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: {
            display: showLegend,
            position: narrow ? "bottom" : "right",
            labels: { boxWidth: 12, font: { size: 11 }, padding: 12 },
          },
          tooltip: {
            callbacks: { label: (ctx) => `${ctx.label}: ${inr(ctx.parsed)}` },
          },
        },
      }}
    />
  );
});
