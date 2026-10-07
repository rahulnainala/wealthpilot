"use client";

import { useEffect, useState } from "react";
import { Radio, Clock, Cpu, Database } from "lucide-react";

import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useTickerStore } from "@/store/useTickerStore";

const ENGINE_POLL_MS = 30_000;

export type EngineStatus = "ok" | "down" | "unknown";

/** Poll the C++ risk engine's liveness (cheap: 2s deadline server-side). */
export function useEngineHealth(): EngineStatus {
  const [status, setStatus] = useState<EngineStatus>("unknown");
  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        const res = await api.engineHealth();
        if (!cancelled) setStatus(res.status === "ok" ? "ok" : "down");
      } catch {
        if (!cancelled) setStatus("down");
      }
    };
    void probe();
    const timer = setInterval(probe, ENGINE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);
  return status;
}

export function StatusBadge({ snapshotTs }: { snapshotTs?: string | null }) {
  const streamStatus = useTickerStore((s) => s.streamStatus);
  const engine = useEngineHealth();

  const config = {
    live: {
      label: "LIVE",
      icon: Radio,
      className: "bg-gain/15 text-gain",
      dot: "bg-gain animate-pulse motion-reduce:animate-none",
    },
    delayed: {
      label: "DELAYED",
      icon: Clock,
      className: "bg-warning/15 text-warning",
      dot: "bg-warning",
    },
    snapshot: {
      label: "SNAPSHOT",
      icon: Database,
      className: "bg-muted text-muted-foreground",
      dot: "bg-muted-foreground/60",
    },
  }[streamStatus];

  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        role="status"
        aria-label={`Data stream: ${config.label.toLowerCase()}`}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium",
          config.className,
        )}
      >
        <span className={cn("size-1.5 rounded-full", config.dot)} />
        <Icon className="size-3" aria-hidden="true" />
        {config.label}
      </span>
      {engine !== "unknown" ? (
        <span
          role="status"
          aria-label={`Risk engine: ${engine === "ok" ? "healthy" : "down"}`}
          title={
            engine === "ok"
              ? "C++ risk engine healthy"
              : "C++ risk engine unreachable — analytics paused"
          }
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium",
            engine === "ok" ? "bg-gain/15 text-gain" : "bg-loss/15 text-loss",
          )}
        >
          <span
            className={cn(
              "size-1.5 rounded-full",
              engine === "ok" ? "bg-gain" : "bg-loss",
            )}
          />
          <Cpu className="size-3" aria-hidden="true" />
          <span className="hidden sm:inline">ENGINE</span>
        </span>
      ) : null}
      {snapshotTs ? (
        <span className="hidden text-muted-foreground lg:inline">
          Snapshot {dateTime(snapshotTs)}
        </span>
      ) : null}
    </div>
  );
}
