"use client";

import { Line } from "react-chartjs-2";

import { CHART_GAIN, ensureChartsRegistered } from "@/components/charts/chartSetup";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import type { ProjectionPoint } from "@/lib/types";

ensureChartsRegistered();

const INDIGO = "#818cf8";

export function ProjectionChart({ points }: { points: ProjectionPoint[] }) {
  const goals = useApi(() => api.goals(), []);
  const refLines = (goals.data ?? [])
    .filter((g) => ["travel", "vehicle"].includes(g.key) && g.target_value)
    .map((g) => ({
      y: g.target_value as number,
      label: `${g.key === "travel" ? "TRV" : "VEH"} ₹${((g.target_value as number) / 100000).toFixed(0)}L`,
      color: CHART_GAIN,
    }));

  // Label every 12th month as a year boundary; blank otherwise.
  const labels = points.map((p) =>
    p.month % 12 === 0 ? `Yr ${p.month / 12}` : "",
  );

  return (
    <Line
      data={{
        labels,
        datasets: [
          {
            label: "p10 (pessimistic)",
            data: points.map((p) => p.p10),
            borderColor: "rgba(129,140,248,0.35)",
            borderWidth: 1,
            pointRadius: 0,
            tension: 0.3,
          },
          {
            label: "p90 (optimistic)",
            data: points.map((p) => p.p90),
            borderColor: "rgba(129,140,248,0.35)",
            borderWidth: 1,
            pointRadius: 0,
            tension: 0.3,
            fill: "-1", // shade the band between p10 and p90
            backgroundColor: "rgba(129,140,248,0.15)",
          },
          {
            label: "Median",
            data: points.map((p) => p.median),
            borderColor: INDIGO,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 3,
            tension: 0.3,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          // Custom plugin config — not in Chart.js's plugin types.
          ...({ wpRefLines: { lines: refLines } } as Record<string, unknown>),
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              title: (items) => {
                const m = points[items[0].dataIndex]?.month ?? 0;
                return `Month ${m} (Yr ${(m / 12).toFixed(1)})`;
              },
              label: (ctx) => `${ctx.dataset.label}: ${inr(ctx.parsed.y ?? 0)}`,
            },
          },
        },
        scales: {
          y: {
            ticks: { font: { size: 11 }, callback: (v) => inr(Number(v)) },
            grid: { color: "rgba(148,163,184,0.14)" },
          },
          x: { grid: { display: false }, ticks: { font: { size: 10 } } },
        },
      }}
    />
  );
}
