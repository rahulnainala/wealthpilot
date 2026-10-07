import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";

import { CHART_GRID, CHART_MUTED_FILL, CHART_TEXT } from "./chartColors";

// Re-exported so chart components (which need chart.js anyway) can keep pulling
// the palette from here. Modules that need *only* a colour must import from
// ./chartColors directly so they don't drag chart.js into their bundle.
export {
  CHART_TEXT,
  CHART_GRID,
  CHART_MUTED_FILL,
  CHART_GAIN,
  CHART_LOSS,
} from "./chartColors";

let registered = false;

// Reference-line plugin: dashed horizontal lines with labels, configured per
// chart via options.plugins.wpRefLines = { lines: [{ y, label, color? }] }.
const wpRefLines = {
  id: "wpRefLines",
  afterDatasetsDraw(chart: Chart) {
    const cfg = (chart.options.plugins as Record<string, unknown> | undefined)?.[
      "wpRefLines"
    ] as { lines?: { y: number; label: string; color?: string }[] } | undefined;
    if (!cfg?.lines?.length) return;
    const { ctx, chartArea, scales } = chart;
    const yScale = scales.y;
    if (!yScale) return;
    for (const line of cfg.lines) {
      const y = yScale.getPixelForValue(line.y);
      if (y < chartArea.top || y > chartArea.bottom) continue;
      ctx.save();
      ctx.strokeStyle = line.color ?? CHART_MUTED_FILL;
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(chartArea.left, y);
      ctx.lineTo(chartArea.right, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = line.color ?? CHART_TEXT;
      ctx.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
      ctx.textAlign = "right";
      ctx.textBaseline = "bottom";
      ctx.fillText(line.label, chartArea.right - 4, y - 2);
      ctx.restore();
    }
  },
};

// Vertical reference-line plugin: solid lines at a category-axis index with a
// label, configured per chart via options.plugins.wpVLines = { lines: [{ x, label, color? }] }.
// Sibling to wpRefLines above, which only draws horizontal (y-value) lines.
const wpVLines = {
  id: "wpVLines",
  afterDatasetsDraw(chart: Chart) {
    const cfg = (chart.options.plugins as Record<string, unknown> | undefined)?.[
      "wpVLines"
    ] as { lines?: { x: number; label: string; color?: string }[] } | undefined;
    if (!cfg?.lines?.length) return;
    const { ctx, chartArea, scales } = chart;
    const xScale = scales.x;
    if (!xScale) return;
    for (const line of cfg.lines) {
      const x = xScale.getPixelForValue(line.x);
      if (x < chartArea.left || x > chartArea.right) continue;
      ctx.save();
      ctx.strokeStyle = line.color ?? CHART_TEXT;
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, chartArea.top);
      ctx.lineTo(x, chartArea.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = line.color ?? CHART_TEXT;
      ctx.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      ctx.fillText(line.label, x + 4, chartArea.top + 2);
      ctx.restore();
    }
  },
};

/** Register Chart.js pieces once (idempotent). */
export function ensureChartsRegistered(): void {
  if (registered) return;
  Chart.register(
    CategoryScale,
    LinearScale,
    BarElement,
    LineElement,
    PointElement,
    ArcElement,
    Filler,
    Tooltip,
    Legend,
    wpRefLines,
    wpVLines,
  );
  Chart.defaults.color = CHART_TEXT;
  Chart.defaults.font.family = "'IBM Plex Mono', ui-monospace, monospace";
  Chart.defaults.borderColor = CHART_GRID;
  registered = true;
}
