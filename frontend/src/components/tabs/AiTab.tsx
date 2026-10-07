"use client";

import { useState } from "react";
import {
  BrainCircuit,
  CalendarDays,
  FileDown,
  MessageSquare,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";

import { AiOpsPanel } from "@/components/AiOpsPanel";
import { DailyPlanPanel } from "@/components/DailyPlanPanel";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PushToggle } from "@/components/PushToggle";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/useApi";
import { api, authHeader } from "@/lib/api";
import { useChatStore } from "@/store/useChatStore";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function ChartVision() {
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function read(file: File) {
    setBusy(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API_BASE}/api/ai/vision`, {
        method: "POST",
        headers: authHeader(),
        body: fd,
      });
      const j = await res.json();
      setResult(j.result);
    } catch {
      setResult("Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Read a chart" description="Upload a chart/screenshot — a local vision model reads it.">
      <label className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-md border border-input px-3 text-sm hover:bg-muted">
        <Upload className="size-4" aria-hidden="true" />
        Choose image
        <input
          type="file"
          accept="image/*"
          className="hidden"
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void read(f);
          }}
        />
      </label>
      <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
        {busy ? "Reading the chart…" : (result ?? "Needs llava on the 3070 (ollama pull llava).")}
      </p>
    </Panel>
  );
}

function StatementUpload() {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [password, setPassword] = useState("");

  async function upload(file: File) {
    setBusy(true);
    setStatus(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (password) fd.append("password", password);
      const res = await fetch(`${API_BASE}/api/ai/upload-statement`, {
        method: "POST",
        headers: authHeader(),
        body: fd,
      });
      const j = await res.json();
      setStatus(
        j.error
          ? j.error
          : `Ingested ${j.chunks_added} chunks (${j.chars} chars). Pilot can now cite it.`,
      );
    } catch {
      setStatus("Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Import Statement"
      description="Upload a broker / CAS PDF — Pilot ingests its text into memory."
    >
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="PDF password (if any)"
          aria-label="PDF password"
          className="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
        />
        <label className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-md border border-input px-3 text-sm hover:bg-muted">
          <Upload className="size-4" aria-hidden="true" />
          Choose PDF
          <input
            type="file"
            accept="application/pdf"
            className="hidden"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void upload(f);
            }}
          />
        </label>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        {busy
          ? "Reading & embedding…"
          : (status ??
            "Text-level import — embeds when the 3070 is on. Password-protected CAS supported.")}
      </p>
    </Panel>
  );
}

function WeeklyReview() {
  const [data, setData] = useState<{ status: string; review: string | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);

  async function load(refresh = false) {
    if (busy) return;
    setBusy(true);
    try {
      setData(await api.aiWeeklyReview(refresh));
    } finally {
      setBusy(false);
    }
  }

  // Auth is header-based (Bearer token), not cookie-based — a plain <a href>
  // can't carry it, so fetch the PDF with the auth header and hand the blob
  // to the browser as a download.
  async function downloadMonthlyReport() {
    if (downloading) return;
    setDownloading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ai/monthly-report`, { headers: authHeader() });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "wealthpilot-monthly-report.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Panel
      title="Weekly Review"
      description="Pilot's Sunday read: what changed, sell plan & goals, one action."
      action={
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void downloadMonthlyReport()}
            disabled={downloading}
            aria-label="Download monthly PDF report"
          >
            <FileDown className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Monthly PDF</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void load(Boolean(data))}
            disabled={busy}
            aria-label="Generate weekly review"
          >
            {data ? <RefreshCw aria-hidden="true" /> : <CalendarDays aria-hidden="true" />}
            <span className="hidden sm:inline">{data ? "Refresh" : "Generate"}</span>
          </Button>
        </div>
      }
    >
      {busy && !data ? (
        <p className="text-sm text-muted-foreground">Pilot is writing your review…</p>
      ) : !data ? (
        <p className="text-sm text-muted-foreground">
          Press Generate for a longer weekly read — auto-written Sundays 07:30 when the 3070 is on.
        </p>
      ) : data.status === "ok" && data.review ? (
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{data.review}</p>
      ) : (
        <p className="text-sm text-muted-foreground">
          {data.status === "unconfigured"
            ? "Start the 3070 (Ollama) to generate the review."
            : "No snapshot yet — sync your portfolio first."}
        </p>
      )}
    </Panel>
  );
}

function KnowledgeSearch() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ source: string; title: string; content: string }[]>([]);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);

  async function run() {
    if (!q.trim() || busy) return;
    setBusy(true);
    try {
      setHits(await api.search(q.trim()));
      setSearched(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Knowledge Search"
      description="Semantic search over Pilot's finance library and portfolio memory."
    >
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. how are REIT distributions taxed?"
          aria-label="Search knowledge"
          className="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
        />
        <Button type="submit" size="sm" disabled={busy || !q.trim()} aria-label="Search">
          <Search aria-hidden="true" />
        </Button>
      </form>
      <div className="mt-4 space-y-3">
        {searched && hits.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="mx-auto max-w-sm text-sm text-muted-foreground">
              No embedded matches — press Learn on AI Systems (needs the 3070 on).
            </p>
          </div>
        ) : null}
        {hits.map((h) => (
          <div key={`${h.source}-${h.title}`} className="rounded-lg border border-border p-3">
            <div className="text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {h.source}
            </div>
            <p className="mt-1.5 text-sm leading-relaxed">{h.content}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function RecentConversations() {
  const state = useApi(() => api.aiChatHistory(10), []);
  const ask = useChatStore((s) => s.setOpen);
  const turns = state.data ?? [];
  return (
    <Panel
      title="Recent Conversations"
      description="What you and Pilot have discussed — the raw material for fine-tuning."
      action={
        <Button variant="outline" size="sm" onClick={() => ask(true)} aria-label="Open chat (⌘J)">
          <MessageSquare aria-hidden="true" />
          <span className="hidden sm:inline">Continue</span>
        </Button>
      }
    >
      {turns.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="mx-auto max-w-sm text-sm text-muted-foreground">
            No conversations yet — press ⌘J and ask Pilot anything.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {turns.slice(-8).map((t, i) => (
            <div
              key={i}
              className={
                t.role === "user"
                  ? "ml-auto w-fit max-w-[85%] rounded-lg bg-primary/15 px-3 py-1.5 text-sm"
                  : "w-fit max-w-[85%] rounded-lg bg-muted px-3 py-1.5 text-sm"
              }
            >
              {t.content.length > 220 ? t.content.slice(0, 220) + "…" : t.content}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

export function AiTab() {
  return (
    <div className="space-y-4">
      <PageHeader
        icon={BrainCircuit}
        title="AI"
        subtitle="Pilot's daily brief, reviews and tools — running on your local 3070."
        action={<PushToggle />}
      />
      <DailyPlanPanel />
      <AiOpsPanel />
      <WeeklyReview />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <KnowledgeSearch />
        <RecentConversations />
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <StatementUpload />
        <ChartVision />
      </div>
    </div>
  );
}
