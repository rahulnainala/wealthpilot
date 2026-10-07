import type { Severity } from "@/lib/types";

export function severityVariant(
  severity: Severity,
): "critical" | "warning" | "info" {
  return severity;
}

export function severityAccent(severity: Severity): string {
  return {
    critical: "border-l-loss",
    warning: "border-l-warning",
    info: "border-l-info",
  }[severity];
}

export function probabilityColor(p: number): string {
  if (p >= 0.7) return "text-gain";
  if (p >= 0.4) return "text-warning";
  return "text-loss";
}
