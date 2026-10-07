"use client";

import { Line } from "react-chartjs-2";

import { ensureChartsRegistered } from "@/components/charts/chartSetup";

ensureChartsRegistered();

export function Sparkline({ data, color }: { data: number[]; color: string }) {
  return (
    <div className="h-10 w-full">
      <Line
        data={{
          labels: data.map((_, i) => i),
          datasets: [
            {
              data,
              borderColor: color,
              borderWidth: 1.5,
              pointRadius: 0,
              tension: 0.4,
              fill: true,
              backgroundColor: `${color}1a`,
            },
          ],
        }}
        options={{
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: false } },
          scales: { x: { display: false }, y: { display: false } },
          elements: { line: { borderJoinStyle: "round" } },
        }}
      />
    </div>
  );
}
