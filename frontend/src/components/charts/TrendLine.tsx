"use client";

import { Line } from "react-chartjs-2";

import { ensureChartsRegistered } from "@/components/charts/chartSetup";

ensureChartsRegistered();

export interface TrendSeries {
  label: string;
  color: string;
  data: number[];
  fill?: boolean;
}

interface Props {
  labels: string[];
  series: TrendSeries[];
  yFormat?: (v: number) => string;
  stacked?: boolean;
}

export function TrendLine({ labels, series, yFormat, stacked }: Props) {
  return (
    <Line
      data={{
        labels,
        datasets: series.map((s) => ({
          label: s.label,
          data: s.data,
          borderColor: s.color,
          backgroundColor: `${s.color}22`,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0.3,
          fill: s.fill ?? false,
        })),
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const y = ctx.parsed.y ?? 0;
                return `${ctx.dataset.label}: ${yFormat ? yFormat(y) : y}`;
              },
            },
          },
        },
        scales: {
          y: {
            stacked: stacked ?? false,
            ticks: {
              font: { size: 11 },
              callback: (v) => (yFormat ? yFormat(Number(v)) : String(v)),
            },
            grid: { color: "rgba(100,116,139,0.12)" },
          },
          x: {
            stacked: stacked ?? false,
            grid: { display: false },
            ticks: { font: { size: 10 }, maxRotation: 0, autoSkip: true },
          },
        },
      }}
    />
  );
}
