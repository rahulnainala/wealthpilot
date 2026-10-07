"use client";

import { useEffect, useState } from "react";
import { NotebookPen } from "lucide-react";

import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { dateOnly } from "@/lib/format";

type Decision = { id: number; action: string; symbol: string | null; note: string; at: string };

/** Phase 35: decision journal — log why you acted; Pilot remembers it. */
export function JournalTab() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [action, setAction] = useState("");
  const [symbol, setSymbol] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.aiDecisions().then(setDecisions).catch(() => {});
  }, []);

  async function save() {
    if (!action.trim() || !note.trim() || busy) return;
    setBusy(true);
    try {
      await api.aiAddDecision({ action: action.trim(), symbol: symbol.trim() || null, note: note.trim() });
      setAction("");
      setSymbol("");
      setNote("");
      setDecisions(await api.aiDecisions());
    } finally {
      setBusy(false);
    }
  }

  const input =
    "min-w-0 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

  return (
    <div className="space-y-4">
      <PageHeader
        icon={NotebookPen}
        title="Journal"
        subtitle="Log why you acted — Pilot recalls your reasoning in chat."
        stats={
          decisions.length
            ? [{ label: "Logged", value: decisions.length, tone: "primary" }]
            : undefined
        }
      />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Panel title="Log a decision" description="Why you acted — Pilot ingests it into memory.">
          <form
            className="space-y-2"
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <div className="flex gap-2">
              <input className={`${input} flex-1`} placeholder="Action (e.g. sold, paused SIP)" value={action} onChange={(e) => setAction(e.target.value)} aria-label="Action" />
              <input className={`${input} w-28`} placeholder="Symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} aria-label="Symbol" />
            </div>
            <textarea className={`${input} w-full`} rows={3} placeholder="Why? What were you thinking?" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Reasoning" />
            <Button type="submit" size="sm" disabled={busy || !action.trim() || !note.trim()}>
              {busy ? "Saving…" : "Log decision"}
            </Button>
          </form>
        </Panel>

        <Panel title="History" description="What you've decided — Pilot can recall these in chat.">
          {decisions.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="mx-auto max-w-sm text-sm text-muted-foreground">
                No decisions yet — log your first above.
              </p>
            </div>
          ) : (
            <ul className="space-y-2.5">
              {decisions.map((d) => (
                <li key={d.id} className="rounded-lg border border-border p-2.5 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">
                      {d.action} {d.symbol ? <span className="text-primary">{d.symbol}</span> : null}
                    </span>
                    <span className="text-2xs tabular-nums text-muted-foreground">{dateOnly(d.at)}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{d.note}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
