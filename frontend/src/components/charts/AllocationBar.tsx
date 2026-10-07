"use client";

import { memo } from "react";
import { Bar } from "react-chartjs-2";

import {
  CHART_MUTED_FILL,
  ensureChartsRegistered,
} from "@/components/charts/chartSetup";
import { BUCKETS, bucketColor } from "@/lib/buckets";

ensureChartsRegistered();

const ORDER = ["growth", "dividend", "mf", "other", "cash"];
const TARGETS: Record<string, number | null> = {
  growth: 33.3,
  dividend: 33.3,
  mf: 33.3,
  other: null,
  cash: null,
};

interface Props {
  bucketValues: Record<string, number>;
  cash: number;
  total: number;
}

export const AllocationBar = memo(function AllocationBar({
  bucketValues,
  cash,
  total,
}: Props) {
  const values: Record<string, number> = { ...bucketValues, cash };
  const labels = ORDER.map((k) => BUCKETS[k].label);
  const currentPct = ORDER.map((k) =>
    total > 0 ? Number((((values[k] ?? 0) / total) * 100).toFixed(1)) : 0,
  );
  const targetPct = ORDER.map((k) => TARGETS[k]);

  const summary = ORDER.map((k, i) => {
    const target = TARGETS[k];
    return `${BUCKETS[k].label} ${currentPct[i]}%${target != null ? ` vs ${target}% target` : ""}`;
  }).join(", ");

  return (
    <Bar
      role="img"
      aria-label={`Allocation versus one-third target bar chart: ${summary}`}
      data={{
        labels,
        datasets: [
          {
            label: "Current %",
            data: currentPct,
            backgroundColor: ORDER.map((k) => bucketColor(k)),
            borderRadius: 6,
            categoryPercentage: 0.6,
            barPercentage: 0.9,
          },
          {
            label: "⅓ Target",
            data: targetPct,
            backgroundColor: CHART_MUTED_FILL,
            borderRadius: 6,
            categoryPercentage: 0.6,
            barPercentage: 0.9,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) =>
                ctx.parsed.y == null ? "" : `${ctx.dataset.label}: ${ctx.parsed.y}%`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { callback: (v) => `${v}%`, font: { size: 11 } },
          },
          x: { grid: { display: false }, ticks: { font: { size: 11 } } },
        },
      }}
    />
  );
});
