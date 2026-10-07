"use client";

import { RefreshCw, Sparkles } from "lucide-react";

import { useToast } from "@/components/ui/toast";
import { Tooltip } from "@/components/ui/tooltip";

import { Panel } from "@/components/Panel";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";

/** Phase-1 AI morning brief. Renders nothing until an AI provider is
 * configured (ANTHROPIC_API_KEY or OLLAMA_URL), so the Overview is
 * unchanged for unconfigured installs. */
export function AiBriefPanel() {
  const state = useApi(() => api.aiBrief(), []);
  const toast = useToast();

  if (state.loading) {
    return (
      <div className="relative">
        <Skeleton className="h-24 w-full" />
        <p className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
          Generating today’s brief on your local model — first load can take a minute…
        </p>
      </div>
    );
  }
  if (state.error || !state.data || state.data.status !== "ok" || !state.data.brief) {
    return null;
  }
  return (
    <Panel
      title="Morning Brief"
      description={`From Pilot · via ${state.data.provider}`}
      action={
        <span className="inline-flex items-center gap-1">
          <Tooltip label="Regenerate on your local model (~1 min)" side="top">
            <button
              type="button"
              aria-label="Regenerate brief"
              onClick={async () => {
                toast("Regenerating the brief on your local model — about a minute.");
                try {
                  await api.aiBrief(true);
                  await state.reload();
                  toast("Morning brief updated.", "success");
                } catch {
                  toast("Couldn't regenerate — model busy or unreachable.", "error");
                }
              }}
              className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <RefreshCw className="size-3.5" aria-hidden="true" />
            </button>
          </Tooltip>
          <Sparkles className="size-4 text-primary" aria-hidden="true" />
        </span>
      }
    >
      <p className="text-sm leading-relaxed">{state.data.brief}</p>
    </Panel>
  );
}
