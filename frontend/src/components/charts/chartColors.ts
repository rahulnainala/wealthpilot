// Canvas colour palette — deliberately chart.js-free so a module that only needs
// a colour (a sparkline stroke, a gain/loss tint) can import it without dragging
// the ~150 kB chart.js bundle into its graph. Chart.js paints to canvas, which
// can't consume CSS custom properties, and its colour math (@kurkle/color)
// doesn't parse oklch — so these mirror the dark-theme --chart-* / --gain /
// --loss tokens in globals.css. Change them together.
export const CHART_TEXT = "#94a3b8"; // slate-400 — legible on light and dark
export const CHART_GRID = "rgba(148, 163, 184, 0.16)";
export const CHART_MUTED_FILL = "rgba(100, 116, 139, 0.25)"; // target/reference bars
export const CHART_GAIN = "#10b981"; // canvas mirror of --gain
export const CHART_LOSS = "#f43f5e"; // canvas mirror of --loss
