"use client";

import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  BrainCircuit,
  Cpu,
  Database,
  GraduationCap,
  MessagesSquare,
  Radio,
} from "lucide-react";

import { Download } from "lucide-react";

import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { dateOnly, istTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const TARGET = 1000;
const POLL_MS = 10_000;

interface Pair {
  messages: { role: string; content: string }[];
  meta: { provider: string; tools: string; ts: string };
}

/** Cockpit training gauge: a 240° instrument arc with the pair count. */
function TrainingGauge({ value, live }: { value: number; live: boolean }) {
  const pct = Math.min(1, value / TARGET);
  const r = 84;
  const start = 150; // degrees; sweep 240°
  const sweep = 240;
  const polar = (deg: number) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return [100 + r * Math.cos(rad), 100 + r * Math.sin(rad)];
  };
  const arc = (from: number, to: number) => {
    const [x1, y1] = polar(from);
    const [x2, y2] = polar(to);
    return `M ${x1} ${y1} A ${r} ${r} 0 ${to - from > 180 ? 1 : 0} 1 ${x2} ${y2}`;
  };
  return (
    <div className="relative mx-auto w-52">
      <svg viewBox="0 0 200 170" role="img" aria-label={`Training progress: ${value} of ${TARGET} pairs`}>
        <path d={arc(start, start + sweep)} fill="none" stroke="var(--muted)" strokeWidth="10" strokeLinecap="round" />
        {pct > 0 ? (
          <path
            d={arc(start, start + sweep * pct)}
            fill="none"
            stroke={pct >= 1 ? "var(--gain)" : "var(--primary)"}
            strokeWidth="10"
            strokeLinecap="round"
          />
        ) : null}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const [x, y] = polar(start + sweep * t);
          return <circle key={t} cx={x} cy={y} r="1.6" fill="var(--muted-foreground)" />;
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pt-3">
        <span className="text-3xl font-semibold tabular-nums">{value}</span>
        <span className="text-2xs uppercase tracking-[0.14em] text-muted-foreground">
          of {TARGET} pairs
        </span>
        {live ? (
          <span className="mt-1 inline-flex items-center gap-1 text-2xs font-semibold uppercase tracking-[0.14em] text-gain">
            <Radio className="size-3 animate-pulse motion-reduce:animate-none" aria-hidden="true" />
            generating
          </span>
        ) : null}
      </div>
    </div>
  );
}

function PipelineNode({
  icon: Icon,
  label,
  value,
  ok,
  tip,
}: {
  icon: typeof Database;
  label: string;
  value: string;
  ok: boolean;
  tip: string;
}) {
  return (
    <Tooltip label={tip} side="top" className="min-w-0 flex-1">
      <div className="flex w-full flex-col items-center gap-1 rounded-lg border border-border bg-card px-2 py-3">
        <Icon className={cn("size-4", ok ? "text-primary" : "text-muted-foreground")} aria-hidden="true" />
        <span className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </span>
        <span className="text-sm font-medium tabular-nums">{value}</span>
        <span className={cn("size-1.5 rounded-full", ok ? "bg-gain" : "bg-muted-foreground/50")} />
      </div>
    </Tooltip>
  );
}

/** Model-quality evals over time (Phase 24). */
function EvalCard() {
  const [evals, setEvals] = useState<Awaited<ReturnType<typeof api.aiEvals>>>([]);
  const [running, setRunning] = useState(false);
  const [ab, setAb] = useState<Awaited<ReturnType<typeof api.aiAbResult>> | null>(null);
  const [abRunning, setAbRunning] = useState(false);

  useEffect(() => {
    api.aiEvals().then(setEvals).catch(() => {});
    api.aiAbResult().then(setAb).catch(() => {});
  }, []);

  const latest = evals.at(-1);
  return (
    <Panel
      title="Model Quality"
      description="Grounding · clean trailer · follow-ups · length — scored over retrains."
    >
      <div className="flex items-center justify-between">
        {latest ? (
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular-nums">
              {latest.score}/{latest.max_score}
            </span>
            <span className="text-xs text-muted-foreground">{latest.model}</span>
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">No evals yet.</span>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={abRunning}
            onClick={() => {
              setAbRunning(true);
              void api.aiAbEval().catch(() => setAbRunning(false));
            }}
            className="rounded-md border border-input px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
          >
            {abRunning ? "A/B (~min)…" : "A/B vs base"}
          </button>
          <button
            type="button"
            disabled={running}
            onClick={() => {
              setRunning(true);
              void api.aiRunEval().catch(() => setRunning(false));
            }}
            className="rounded-md border border-input px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
          >
            {running ? "Running (~min)…" : "Run eval"}
          </button>
        </div>
      </div>
      {ab?.recommendation ? (
        <p
          className={cn(
            "mt-3 rounded-lg border px-3 py-2 text-xs",
            ab.winner === ab.candidate
              ? "border-gain/40 bg-gain/[0.08]"
              : "border-warning/40 bg-warning/[0.08]",
          )}
        >
          {ab.recommendation}
        </p>
      ) : null}
      {evals.length > 1 ? (
        <div className="mt-3 flex items-end gap-1" aria-hidden="true">
          {evals.map((e, i) => (
            <div
              key={i}
              title={`${e.score}/${e.max_score} · ${dateOnly(e.at)}`}
              className="w-full rounded-sm bg-primary/60"
              style={{ height: `${(e.score / e.max_score) * 40 + 4}px` }}
            />
          ))}
        </div>
      ) : null}
    </Panel>
  );
}

/** Knowledge Hub: how Pilot learns, as a live instrument panel. */
export function LearnTab() {
  const [status, setStatus] = useState<Awaited<ReturnType<typeof api.aiStatus>> | null>(null);
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [climbing, setClimbing] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      // The tab shell keeps this mounted-but-hidden once visited (see
      // ui/tabs.tsx's keep-alive TabsContent) — skip the fetch while the
      // panel isn't the visible one, instead of polling forever in the background.
      if (rootRef.current && rootRef.current.offsetParent === null) return;
      try {
        const [s, p] = await Promise.all([api.aiStatus(), api.trainingData()]);
        if (cancelled) return;
        setStatus((prev) => {
          if (prev) setClimbing(s.training_pairs > prev.training_pairs);
          return s;
        });
        setPairs(p.slice(-6).reverse());
      } catch {
        /* backend briefly away — keep last view */
      }
    };
    void poll();
    const t = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  if (!status) {
    // Was `return null` — a blank tab during the first poll. Mirror the layout
    // (header, stepper, the 2/3-split instrument row, eval, feed) instead.
    return (
      <div ref={rootRef} className="space-y-4">
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-16 rounded-xl" />
        <div className="grid gap-4 lg:grid-cols-5">
          <Skeleton className="h-64 rounded-xl lg:col-span-2" />
          <Skeleton className="h-64 rounded-xl lg:col-span-3" />
        </div>
        <Skeleton className="h-40 rounded-xl" />
      </div>
    );
  }

  // Live rate from the newest pair timestamps -> pairs/hour and ETA to target.
  const ts = pairs.map((p) => new Date(p.meta.ts).getTime()).filter((n) => !isNaN(n));
  let rate: number | null = null;
  if (ts.length >= 3) {
    const spanH = (Math.max(...ts) - Math.min(...ts)) / 3.6e6;
    if (spanH > 0.005) rate = (ts.length - 1) / spanH;
  }
  const etaH = rate && rate > 0 ? (TARGET - status.training_pairs) / rate : null;

  const phase = status.custom_model_present ? 2 : status.training_pairs >= TARGET ? 1 : 0;
  const STEPS = [
    { label: "Collect", detail: `${status.training_pairs}/${TARGET} pairs` },
    { label: "Train", detail: "~2h on the 3070 (ai-training/)" },
    { label: "Fly", detail: "OLLAMA_MODEL=wealthpilot" },
  ];

  return (
    <div ref={rootRef} className="space-y-4">
      <PageHeader
        icon={GraduationCap}
        title="Learn"
        subtitle="How Pilot learns — training data, embeddings and model quality, live."
        stats={[
          {
            label: "Model",
            value: status.custom_model_present ? "Ready" : "Locked",
            tone: status.custom_model_present ? "gain" : "default",
          },
          {
            label: "3070",
            value: status.ollama_reachable ? "Online" : "Offline",
            tone: status.ollama_reachable ? "gain" : "loss",
          },
        ]}
      />
      <div className="flex items-center gap-0 rounded-xl border border-border bg-card px-5 py-3">
        {STEPS.map((st, i) => (
          <div key={st.label} className="flex min-w-0 flex-1 items-center">
            <div className="flex min-w-0 items-center gap-2.5">
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full text-2xs font-semibold",
                  i < phase
                    ? "bg-gain text-primary-foreground"
                    : i === phase
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground",
                )}
              >
                {i + 1}
              </span>
              <span className="min-w-0">
                <span
                  className={cn(
                    "block text-2xs font-semibold uppercase tracking-[0.14em]",
                    i === phase ? "text-primary" : "text-muted-foreground",
                  )}
                >
                  {st.label}
                </span>
                <span className="block truncate text-xs tabular-nums text-muted-foreground">
                  {st.detail}
                </span>
              </span>
            </div>
            {i < STEPS.length - 1 ? (
              <div className={cn("mx-3 h-px flex-1", i < phase ? "bg-gain" : "bg-border")} />
            ) : null}
          </div>
        ))}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-5">
        <Panel
          title="Flight School"
          description={
            rate
              ? `~${rate.toFixed(0)} pairs/hr · ETA ${etaH && etaH < 48 ? etaH.toFixed(1) + "h" : ((etaH ?? 0) / 24).toFixed(1) + " days"} of GPU time`
              : "Pairs toward your custom model."
          }
          className="lg:col-span-2"
        >
          <TrainingGauge value={status.training_pairs} live={climbing} />
          <a
            href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/ai/training-data`}
            target="_blank"
            rel="noreferrer"
            className="mx-auto mt-1 flex w-fit items-center gap-1.5 text-xs font-medium text-primary hover:underline"
          >
            <Download className="size-3.5" aria-hidden="true" />
            Export dataset
          </a>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            {status.training_pairs >= TARGET
              ? "Threshold reached — run the fine-tune (ai-training/README.md)."
              : climbing
                ? "The 3070 is answering the question bank right now."
                : "Resume: docker compose exec -d backend python scripts/generate_training.py --target 1000"}
          </p>
          {status.custom_model_present ? (
            <div
              className={cn(
                "mt-3 rounded-lg border px-3 py-2 text-center text-xs",
                status.retrain_recommended
                  ? "border-warning/40 bg-warning/[0.08] text-foreground"
                  : "border-border text-muted-foreground",
              )}
            >
              {status.retrain_recommended ? (
                <>
                  <span className="font-semibold text-warning">Retrain recommended</span> —{" "}
                  {status.pairs_since_train} new pairs since the last train.
                </>
              ) : (
                <>{status.pairs_since_train} new pairs since the last train (retrain at 150+).</>
              )}
            </div>
          ) : null}
        </Panel>

        <Panel
          title="Learning Pipeline"
          description="How knowledge flows into Pilot — every stage live."
          className="lg:col-span-3"
        >
          <div className="flex items-stretch gap-2">
            <PipelineNode icon={BookOpen} label="Corpus" value="13 docs" ok tip="Finance library + your notes in docs/knowledge/" />
            <PipelineNode
              icon={Database}
              label="Embedded"
              value={`${status.chunks_embedded}/${status.chunks_total}`}
              ok={status.chunks_embedded === status.chunks_total}
              tip="RAG vectors in pgvector — pending chunks wait for the GPU"
            />
            <PipelineNode
              icon={BrainCircuit}
              label="Memory"
              value={status.last_memory_date?.slice(5) ?? "—"}
              ok={Boolean(status.last_memory_date)}
              tip="Latest distilled portfolio note (nightly 20:30 or Learn button)"
            />
            <PipelineNode
              icon={MessagesSquare}
              label="Pairs"
              value={String(status.training_pairs)}
              ok={status.training_pairs > 0}
              tip="Grounded conversations logged for fine-tuning"
            />
            <PipelineNode
              icon={GraduationCap}
              label="Model"
              value={status.custom_model_present ? "ready" : "locked"}
              ok={status.custom_model_present}
              tip="wealthpilot appears here after the LoRA run"
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2">
            <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
              <Cpu className="size-3.5" aria-hidden="true" />
              <span className={cn("size-1.5 rounded-full", status.ollama_reachable ? "bg-gain" : "bg-loss")} />
              3070 {status.ollama_reachable ? "online" : "offline"}
            </span>
            {status.loaded.map((m) => (
              <span key={m.name} className="text-xs tabular-nums text-muted-foreground">
                {m.name} · {m.vram_gb}GB VRAM
              </span>
            ))}
          </div>
        </Panel>
      </div>

      <EvalCard />

      <Panel title="Live Feed" description="Newest grounded Q&A entering the dataset · 10s refresh">
        {pairs.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="mx-auto max-w-sm text-sm text-muted-foreground">
              No pairs yet — chat with Pilot (⌘J) or start the generator.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {pairs.map((p, i) => {
              const q = p.messages.find((m) => m.role === "user")?.content ?? "";
              const a = (p.messages.find((m) => m.role === "assistant")?.content ?? "")
                .split(/FOLLOW-UPS:/i)[0]
                .trim();
              return (
                <div key={`${p.meta.ts}-${i}`} className="rounded-lg border border-border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium">{q}</p>
                    <span className="shrink-0 text-2xs tabular-nums text-muted-foreground">
                      {istTime(p.meta.ts)}
                    </span>
                  </div>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {a.length > 240 ? a.slice(0, 240) + "…" : a}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
