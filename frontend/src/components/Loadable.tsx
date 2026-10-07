import * as React from "react";

import { Skeleton } from "@/components/ui/skeleton";
import type { ApiState } from "@/hooks/useApi";
import { ApiError } from "@/lib/api";

interface Props<T> {
  state: ApiState<T>;
  skeleton?: React.ReactNode;
  emptyMessage?: string;
  children: (data: T) => React.ReactNode;
}

export function Loadable<T>({ state, skeleton, emptyMessage, children }: Props<T>) {
  if (state.loading) {
    // rounded-xl so the placeholder matches the card it becomes (Skeleton
    // itself defaults to rounded-md).
    return <>{skeleton ?? <Skeleton className="h-40 w-full rounded-xl" />}</>;
  }
  if (state.error || state.data == null) {
    // A 503 carries a specific, user-facing reason (e.g. risk engine down) —
    // show it instead of the generic refresh hint.
    const unavailable =
      state.error instanceof ApiError && state.error.status === 503
        ? state.error.message
        : null;
    // Composed, centred empty/error state with a measure-capped line, rather
    // than a bare left-aligned paragraph — the same treatment across every
    // panel that defers its empty state here.
    return (
      <div className="px-4 py-8 text-center">
        <p className="mx-auto max-w-sm text-sm text-muted-foreground">
          {unavailable ?? emptyMessage ?? "Couldn't load — refresh the portfolio first."}
        </p>
      </div>
    );
  }
  return <>{children(state.data)}</>;
}
