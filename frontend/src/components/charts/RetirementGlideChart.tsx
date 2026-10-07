"use client";

import { useState } from "react";
import { Line } from "react-chartjs-2";

import { CHART_LOSS, ensureChartsRegistered } from "@/components/charts/chartSetup";
import { inr } from "@/lib/format";
import { cn } from "@/lib/utils";

ensureChartsRegistered();

const INDIGO = "#818cf8";
const INDIGO_BAND_BORDER = "rgba(129,140,248,0.35)";
const INDIGO_BAND_FILL = "rgba(129,140,248,0.15)";
const LOSS_BAND_BORDER = "rgba(244,63,94,0.4)";
const LOSS_BAND_FILL = "rgba(244,63,94,0.13)";

export interface RetirementBand {
  month: number;
  p10: number;
  median: number;
  p90: number;
  p10_today: number;
  median_today: number;
  p90_today: number;
}

/**
 * Yearly p10/median/p90 fan across accumulation *and* drawdown on one chart —
 * the whole journey, not just the retirement-date snapshot. The band past the
 * retirement-boundary marker switches to a loss-toned color so drawdown reads
 * at a glance, since that's the phase where the corpus can run out.
 */
export function RetirementGlideChart({
  bands,
  retirementMonth,
}: {
  bands: RetirementBand[];
  retirementMonth: number;
}) {
  const [todaysMoney, setTodaysMoney] = useState(true);

  const pick = (b: RetirementBand) =>
    todaysMoney
      ? { p10: b.p10_today, median: b.median_today, p90: b.p90_today }
      : { p10: b.p10, median: b.median, p90: b.p90 };

  const retirementIdx = bands.findIndex((b) => b.month >= retirementMonth);
  const inDrawdown = (idx: number) => retirementIdx >= 0 && idx >= retirementIdx;

  const labels = bands.map((b) => `Yr ${(b.month / 12).toFixed(0)}`);

  return (
    <div>
      <div className="mb-2 flex items-center justify-end gap-2">
        <span className="text-2xs text-muted-foreground">Show in</span>
        <div className="inline-flex overflow-hidden rounded-md border border-border text-2xs">
          <button
            type="button"
            onClick={() => setTodaysMoney(true)}
            className={cn(
              "px-2 py-1 font-medium transition-colors",
              todaysMoney
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            Today&apos;s money
          </button>
          <button
            type="button"
            onClick={() => setTodaysMoney(false)}
            className={cn(
              "px-2 py-1 font-medium transition-colors",
              !todaysMoney
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            Future ₹
          </button>
        </div>
      </div>
      <div className="h-72">
        <Line
          data={{
            labels,
            datasets: [
              {
                label: "p10",
                data: bands.map((b) => pick(b).p10),
                borderColor: INDIGO_BAND_BORDER,
                borderWidth: 1,
                pointRadius: 0,
                tension: 0.3,
                segment: {
                  borderColor: (ctx) =>
                    inDrawdown(ctx.p0DataIndex) ? LOSS_BAND_BORDER : INDIGO_BAND_BORDER,
                },
              },
              {
                label: "p90",
                data: bands.map((b) => pick(b).p90),
                borderColor: INDIGO_BAND_BORDER,
                borderWidth: 1,
                pointRadius: 0,
                tension: 0.3,
                fill: "-1", // shade the band between p10 and p90
                backgroundColor: INDIGO_BAND_FILL,
                segment: {
                  borderColor: (ctx) =>
                    inDrawdown(ctx.p0DataIndex) ? LOSS_BAND_BORDER : INDIGO_BAND_BORDER,
                  backgroundColor: (ctx) =>
                    inDrawdown(ctx.p0DataIndex) ? LOSS_BAND_FILL : INDIGO_BAND_FILL,
                },
              },
              {
                label: "Median",
                data: bands.map((b) => pick(b).median),
                borderColor: INDIGO,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 3,
                tension: 0.3,
                segment: {
                  borderColor: (ctx) => (inDrawdown(ctx.p0DataIndex) ? CHART_LOSS : INDIGO),
                },
              },
            ],
          }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
              // Custom plugin config — not in Chart.js's plugin types.
              ...({
                wpVLines: {
                  lines:
                    retirementIdx >= 0
                      ? [{ x: retirementIdx, label: "Retirement", color: CHART_LOSS }]
                      : [],
                },
              } as Record<string, unknown>),
              legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
              tooltip: {
                callbacks: {
                  title: (items) => {
                    const b = bands[items[0].dataIndex];
                    const m = b?.month ?? 0;
                    const phase = m >= retirementMonth ? " · drawdown" : "";
                    return `Year ${(m / 12).toFixed(0)}${phase}`;
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
      </div>
    </div>
  );
}
