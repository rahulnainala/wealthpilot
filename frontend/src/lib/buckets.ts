export interface BucketMeta {
  key: string;
  label: string;
  color: string;
}

// Canonical bucket palette for canvas charts (Chart.js can't consume CSS
// custom properties or oklch). These hexes deliberately mirror the dark-theme
// --chart-* tokens in globals.css — change them together. DOM elements should
// prefer CSS tokens directly; canvas consumers use these.
export const BUCKETS: Record<string, BucketMeta> = {
  growth: { key: "growth", label: "Growth", color: "#10b981" },
  dividend: { key: "dividend", label: "Dividend", color: "#0ea5e9" },
  mf: { key: "mf", label: "Mutual Funds", color: "#8b5cf6" },
  other: { key: "other", label: "Gold / Other", color: "#f59e0b" },
  cash: { key: "cash", label: "Cash", color: "#64748b" },
};

/** The three-way split whose target is ~⅓ each. */
export const CORE_BUCKETS = ["growth", "dividend", "mf"] as const;

export function bucketLabel(key: string): string {
  return BUCKETS[key]?.label ?? key;
}

export function bucketColor(key: string): string {
  return BUCKETS[key]?.color ?? "#94a3b8";
}
