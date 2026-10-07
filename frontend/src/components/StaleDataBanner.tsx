"use client";

import { AlertTriangle } from "lucide-react";

import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import type { SnapshotHealth } from "@/lib/types";

/**
 * Warns when the app's view of the portfolio has stopped updating.
 *
 * Scheduled snapshots fail silently whenever the daily Zerodha token has
 * expired: the UI keeps rendering the last good one, so every number still
 * looks current. That gap is not cosmetic — a position can cross its sell
 * threshold, and the sell queue will happily show a stale "Hold" throughout.
 *
 * Deliberately separate from `ReconnectBanner`: a live session with a dead
 * scheduler still leaves the data stale, and a reconnect prompt alone would
 * imply the problem was fixed the moment you logged back in.
 */
export function StaleDataBanner() {
  const { data } = useApi<SnapshotHealth>(() => api.snapshotHealth(), []);
  if (!data) return null;

  const missed = data.failures_since_ok;
  if (!data.is_stale && missed === 0) return null;

  const age =
    data.hours_since_ok == null
      ? "never"
      : data.hours_since_ok < 48
        ? `${Math.round(data.hours_since_ok)}h ago`
        : `${Math.round(data.hours_since_ok / 24)} days ago`;

  // `status` (polite), not `alert`: this is persistent page context that
  // appears when a fetch resolves, not an urgent interruption. Reserve the
  // assertive `alert` for the expired-session prompt, which needs action now —
  // firing both assertively on load would talk over each other.
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm text-warning"
    >
      <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
      <span className="font-semibold">
        {data.is_stale ? "Portfolio data is stale." : "Missed refreshes."}
      </span>
      <span className="tabular-nums">
        Last good snapshot {age}
        {data.last_ok_ts ? ` (${dateTime(data.last_ok_ts)})` : ""}.
      </span>
      {missed > 0 ? (
        <span className="tabular-nums">
          {missed} scheduled refresh{missed === 1 ? "" : "es"} failed since — prices
          and sell signals below may be out of date.
        </span>
      ) : null}
    </div>
  );
}
