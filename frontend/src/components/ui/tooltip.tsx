"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

/** Instrument tooltip: shows on hover and keyboard focus. Pure CSS placement
 * (no portal) — suited to rail items, badges, and table headers. */
export function Tooltip({
  label,
  side = "right",
  children,
  className,
}: {
  label: string;
  side?: "right" | "top" | "bottom";
  children: React.ReactNode;
  className?: string;
}) {
  const pos = {
    right: "left-full top-1/2 ml-2 -translate-y-1/2",
    top: "bottom-full left-1/2 mb-1.5 -translate-x-1/2",
    bottom: "top-full left-1/2 mt-1.5 -translate-x-1/2",
  }[side];
  return (
    <span className={cn("group/tip relative inline-flex", className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 hidden whitespace-nowrap rounded-md border border-border bg-popover px-2 py-1 text-2xs text-popover-foreground shadow-md",
          "group-hover/tip:block group-focus-within/tip:block",
          pos,
        )}
      >
        {label}
      </span>
    </span>
  );
}
