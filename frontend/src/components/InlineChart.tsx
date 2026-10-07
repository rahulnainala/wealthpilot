"use client";

import { useEffect, useState } from "react";
import { Bar, Doughnut } from "react-chartjs-2";

import { ensureChartsRegistered } from "@/components/charts/chartSetup";
import { api } from "@/lib/api";

const COLORS = [
  "#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#f87171", "#60a5fa", "#f472b6", "#94a3b8",
];

/** Phase 27: renders a chart spec from /api/ai/chart inline in a chat reply. */
export function InlineChart({ kind }: { kind: string }) {
  ensureChartsRegistered();
  const [spec, setSpec] = useState<Awaited<ReturnType<typeof api.aiChart>> | null>(null);

  useEffect(() => {
    api.aiChart(kind).then(setSpec).catch(() => {});
  }, [kind]);

  if (!spec) return null;
  const labels = spec.series.map((s) => s.label);
  const values = spec.series.map((s) => s.value);
  const data = { labels, datasets: [{ data: values, backgroundColor: COLORS, borderWidth: 0 }] };

  return (
    <div className="mt-2 rounded-lg border border-border bg-card p-3">
      <p className="mb-2 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {spec.title}
      </p>
      <div className="mx-auto max-w-[240px]">
        {spec.type === "donut" ? (
          <Doughnut
            data={data}
            options={{ plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } } } }}
          />
        ) : (
          <Bar
            data={data}
            options={{
              plugins: { legend: { display: false } },
              scales: { x: { ticks: { font: { size: 9 } } } },
            }}
          />
        )}
      </div>
    </div>
  );
}
