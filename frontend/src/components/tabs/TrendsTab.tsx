"use client";

import { LineChart } from "lucide-react";

import { ProjectionChart } from "@/components/charts/ProjectionChart";
import { TrendLine } from "@/components/charts/TrendLine";
import { Loadable } from "@/components/Loadable";
import { PageHeader, type PageStat } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { TimeTravelPanel } from "@/components/TimeTravelPanel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { BUCKETS } from "@/lib/buckets";
import { dateOnly, inr } from "@/lib/format";
import type { ProjectionPoint, SnapshotSummary } from "@/lib/types";

const BUCKET_KEYS = ["growth", "dividend", "mf", "other"];

function History({ history }: { history: SnapshotSummary[] }) {
  if (history.length < 2) {
    return (
      <Panel title="History">
        <p className="text-sm text-muted-foreground">
          Historical trends build as daily snapshots accumulate ({history.length} so
          far). The forward projection above works right now.
        </p>
      </Panel>
    );
  }

  const labels = history.map((s) => dateOnly(s.ts));
  const bucketSeries = BUCKET_KEYS.map((key) => ({
    label: BUCKETS[key].label,
    color: BUCKETS[key].color,
    fill: true,
    data: history.map((s) => {
      const total = Object.values(s.bucket_values).reduce((a, b) => a + b, 0) + s.cash;
      return total > 0
        ? Number((((s.bucket_values[key] ?? 0) / total) * 100).toFixed(1))
        : 0;
    }),
  }));

  return (
    <>
      <Panel title="Total Value Over Time" bodyClassName="h-72">
        <TrendLine
          labels={labels}
          series={[
            {
              label: "Total Value",
              color: "#6366f1",
              fill: true,
              data: history.map((s) => s.total_value),
            },
            {
              label: "Invested",
              color: "#94a3b8",
              data: history.map((s) => s.invested),
            },
          ]}
          yFormat={(v) => inr(v)}
        />
      </Panel>
      <Panel title="Bucket Allocation Over Time" bodyClassName="h-72">
        <TrendLine labels={labels} series={bucketSeries} stacked yFormat={(v) => `${v}%`} />
      </Panel>
    </>
  );
}

export function TrendsTab() {
  const projection = useApi<ProjectionPoint[]>(() => api.projection(10), []);
  const history = useApi<SnapshotSummary[]>(() => api.snapshotHistory(90), []);

  // Anchor the tab: how much history it's built on, and where the 10-year
  // Monte Carlo median lands — the two numbers the charts below elaborate.
  const projectedMedian = projection.data?.at(-1)?.median;
  const stats: PageStat[] = [];
  if (history.data) {
    stats.push({ label: "Snapshots", value: String(history.data.length) });
  }
  if (projectedMedian != null) {
    stats.push({ label: "Projected 10y", value: inr(projectedMedian), tone: "primary" });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={LineChart}
        title="Trends"
        subtitle="Where the portfolio is headed and where it's been — projection and history."
        stats={stats.length ? stats : undefined}
      />
      <Panel
        title="Projected Portfolio Value"
        description="10-year forward Monte Carlo (C++ engine): median value with a p10–p90 confidence band, assuming you hold as-is."
        bodyClassName="h-72"
      >
        <Loadable
          state={projection}
          emptyMessage="Refresh the portfolio to generate a projection."
        >
          {(points) => <ProjectionChart points={points} />}
        </Loadable>
      </Panel>

      <Loadable state={history}>
        {(hist) => <History history={hist} />}
      </Loadable>

      <TimeTravelPanel />
    </div>
  );
}
