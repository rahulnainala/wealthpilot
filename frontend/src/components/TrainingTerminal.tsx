"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { API_BASE } from "@/lib/config";

const MAX_LINES = 300;

/**
 * Live tail of the training generator's log output — an SSE connection to
 * /api/ai/train/logs/stream, rendered as a small scrolling readout. Stays
 * mounted (not just while a run is active) so the last run's output is still
 * readable, and reconnects automatically (native EventSource behavior) if
 * the backend restarts mid-run.
 */
export function TrainingTerminal({ active }: { active: boolean }) {
  const [lines, setLines] = useState<string[]>([]);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/ai/train/logs/stream`);
    es.onmessage = (e) => {
      setLines((prev) => {
        const next = [...prev, e.data];
        return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
      });
    };
    return () => es.close();
  }, []);

  useEffect(() => {
    const el = boxRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  if (lines.length === 0 && !active) return null;

  return (
    <div className="mt-3.5">
      <div className="mb-1.5 flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        <span
          className={cn(
            "size-1.5 rounded-full",
            active ? "animate-pulse bg-gain motion-reduce:animate-none" : "bg-muted-foreground/50",
          )}
          aria-hidden="true"
        />
        Training terminal
      </div>
      <div
        ref={boxRef}
        role="log"
        aria-live="polite"
        aria-label="Training generator output"
        className="h-40 overflow-y-auto rounded-lg border border-border bg-background p-2.5 font-mono text-2xs leading-relaxed text-foreground/80"
      >
        {lines.length === 0 ? (
          <p className="text-muted-foreground/60">Waiting for output…</p>
        ) : (
          lines.map((l, i) => (
            <div key={i} className="whitespace-pre-wrap break-all">
              {l}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
