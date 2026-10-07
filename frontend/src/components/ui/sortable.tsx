"use client";

import { useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { TableHead } from "@/components/ui/table";

type Dir = "asc" | "desc";
export type Accessor<T> = (row: T) => number | string;

export interface SortState<T> {
  key: string;
  dir: Dir;
  sorted: T[];
  toggle: (key: string) => void;
}

/** Client-side sorting over a row set with named accessors. */
export function useSort<T>(
  rows: T[],
  accessors: Record<string, Accessor<T>>,
  defaultKey: string,
  defaultDir: Dir = "desc",
): SortState<T> {
  const [key, setKey] = useState(defaultKey);
  const [dir, setDir] = useState<Dir>(defaultDir);

  // Callers pass accessors as an inline literal; capture the first instance so
  // the memo below keys off data and sort state, not object identity.
  const accessorsRef = useRef(accessors);
  accessorsRef.current = accessors;

  const sorted = useMemo(() => {
    const accessor = accessorsRef.current[key] ?? accessorsRef.current[defaultKey];
    return [...rows].sort((a, b) => {
      const av = accessor(a);
      const bv = accessor(b);
      const cmp =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv));
      return dir === "asc" ? cmp : -cmp;
    });
  }, [rows, key, dir, defaultKey]);

  const toggle = (k: string) => {
    if (k === key) {
      setDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setKey(k);
      setDir("desc");
    }
  };

  return { key, dir, sorted, toggle };
}

export function SortHead<T>({
  label,
  sortKey,
  sort,
  className,
}: {
  label: string;
  sortKey: string;
  sort: SortState<T>;
  className?: string;
}) {
  const active = sort.key === sortKey;
  return (
    <TableHead
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
      className={className}
    >
      <button
        type="button"
        onClick={() => sort.toggle(sortKey)}
        className="inline-flex cursor-pointer select-none items-center gap-1 hover:text-foreground"
      >
        {label}
        {active ? (
          sort.dir === "asc" ? (
            <ChevronUp className="size-3" aria-hidden="true" />
          ) : (
            <ChevronDown className="size-3" aria-hidden="true" />
          )
        ) : null}
      </button>
    </TableHead>
  );
}
