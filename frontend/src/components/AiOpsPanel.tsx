"use client";

import { useState } from "react";
import { BrainCircuit, Download, FlaskConical, Play, RefreshCw, Send, Square } from "lucide-react";

import { useToast } from "@/components/ui/toast";

import { Panel } from "@/components/Panel";
import { TrainingTerminal } from "@/components/TrainingTerminal";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { API_BASE } from "@/lib/config";


function Stat({ label, value, tip }: { label: string; value: string; tip: string }) {
  return (
    <Tooltip label={tip} side="top">
      <div className="flex items-baseline gap-2">
        <span className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </span>
        <span className="text-sm font-medium tabular-nums">{value}</span>
      </div>
    </Tooltip>
  );
}

/** Makes the invisible AI loops visible: RAG, memory, LoRA progress. */
export function AiOpsPanel() {
  const state = useApi(() => api.aiStatus(), []);
  const toast = useToast();
  const [learning, setLearning] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [evaling, setEvaling] = useState(false);

  async function learnNow() {
    if (learning) return;
    setLearning(true);
    toast("Learning: distilling today's portfolio and embedding on your 3070…");
    try {
      const r = await api.aiLearn();
      toast(
        `Learned — memory ${r.distilled ? "updated" : "unchanged"}, ${r.chunks_added} new chunks, ${r.embedded} embedded.`,
        "success",
      );
      await state.reload();
    } catch {
      toast("Learning run failed — is the backend up? (Embedding waits if the 3070 is busy.)", "error");
    } finally {
      setLearning(false);
    }
  }

  async function togglePush(running: boolean) {
    if (pushing) return;
    setPushing(true);
    try {
      if (running) {
        await api.aiTrainStop();
        toast("Stopped the training generator.", "success");
      } else {
        await api.aiTrainStart();
        toast("Pushed to the 3070 — generating grounded Q&A pairs toward the LoRA dataset.", "success");
      }
      await state.reload();
    } catch {
      toast("Couldn't reach the backend to start/stop the generator.", "error");
    } finally {
      setPushing(false);
    }
  }

  async function refreshSnapshot() {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await api.refreshSnapshot();
      toast("Snapshot saved — holdings and analytics are current.", "success");
    } catch {
      toast("Snapshot refresh failed — check the backend and try again.", "error");
    } finally {
      setRefreshing(false);
    }
  }

  async function runEval() {
    if (evaling) return;
    setEvaling(true);
    toast("Eval started — scoring the live model (~1 min)…");
    try {
      await api.aiRunEval();
    } catch {
      toast("Couldn't start the eval run.", "error");
    } finally {
      setEvaling(false);
    }
  }

  if (!state.data) return null;
  const s = state.data;
  return (
    <Panel
      title="AI Systems"
      description="The learning loops running behind the app."
      action={
        <span className="inline-flex items-center gap-1.5">
          <Tooltip label="Run the learning loop now (distill + embed)" side="top">
            <button
              type="button"
              aria-label="Learn now"
              disabled={learning}
              onClick={learnNow}
              className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-primary/15 hover:text-primary disabled:opacity-50"
            >
              <Play className="size-3.5" aria-hidden="true" />
            </button>
          </Tooltip>
          <span
            className={cn(
              "size-1.5 rounded-full",
              s.ollama_reachable ? "bg-gain" : "bg-muted-foreground/60",
            )}
          />
          <BrainCircuit className="size-4 text-muted-foreground" aria-hidden="true" />
        </span>
      }
    >
      <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
        <Stat label="Model" value={s.model} tip="Local model on the 3070 (Ollama)" />
        <Stat
          label="Knowledge"
          value={`${s.chunks_embedded}/${s.chunks_total}`}
          tip="RAG chunks embedded / total — pending ones wait for the 3070"
        />
        <Stat
          label="Memory"
          value={s.last_memory_date ?? "—"}
          tip="Latest distilled portfolio note (nightly 20:30 IST)"
        />
        <Stat
          label="Training"
          value={`${s.training_pairs}/1000`}
          tip="Chat pairs collected toward LoRA fine-tuning"
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3.5">
        <Tooltip
          label={
            s.training_generator_running
              ? "Stop the background generator"
              : "Start generating grounded Q&A pairs — each one runs on the 3070"
          }
          side="top"
        >
          <Button
            variant={s.training_generator_running ? "destructive" : "outline"}
            size="sm"
            disabled={pushing}
            onClick={() => void togglePush(s.training_generator_running)}
            aria-label={s.training_generator_running ? "Stop training generator" : "Push to 3070"}
          >
            {s.training_generator_running ? (
              <Square aria-hidden="true" />
            ) : (
              <Send aria-hidden="true" />
            )}
            {s.training_generator_running ? "Stop" : "Push to 3070"}
          </Button>
        </Tooltip>
        <Button
          variant="outline"
          size="sm"
          disabled={refreshing}
          onClick={() => void refreshSnapshot()}
          aria-label="Save a snapshot now"
        >
          <RefreshCw aria-hidden="true" />
          {refreshing ? "Saving…" : "Save snapshot"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={evaling}
          onClick={() => void runEval()}
          aria-label="Run model quality eval"
        >
          <FlaskConical aria-hidden="true" />
          {evaling ? "Running…" : "Run eval"}
        </Button>
        <a
          href={`${API_BASE}/api/ai/training-data`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-7 items-center gap-1 rounded-[min(var(--radius-md),12px)] border border-border bg-background px-2.5 text-[0.8rem] font-medium hover:bg-muted"
        >
          <Download className="size-3.5" aria-hidden="true" />
          Export dataset
        </a>
      </div>

      <TrainingTerminal active={s.training_generator_running} />
    </Panel>
  );
}
