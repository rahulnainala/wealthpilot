"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BookmarkPlus, MessageSquare, Mic, Send, TriangleAlert, Volume2, VolumeX, X } from "lucide-react";

import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { API_BASE } from "@/lib/config";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/store/useChatStore";

// Lazy so chart.js stays out of the header / first-load bundle — an inline chart
// only appears when a chat reply actually contains a [[chart:…]] tag. InlineChart
// renders null until its own fetch resolves, so no loading placeholder is needed.
const InlineChart = dynamic(
  () => import("@/components/InlineChart").then((m) => m.InlineChart),
  { ssr: false },
);

const FOLLOW_RE = /\n?\s*FOLLOW-UPS:\s*(.+)\s*$/i;
const CHART_RE = /\[\[chart:(\w+)\]\]/g;

function stripFollowUps(text: string): { text: string; followUps: string[] } {
  const m = text.match(FOLLOW_RE);
  if (!m) return { text, followUps: [] };
  return {
    text: text.replace(FOLLOW_RE, "").trim(),
    followUps: m[1].split("|").map((q) => q.trim()).filter(Boolean).slice(0, 3),
  };
}

interface Turn {
  role: "user" | "assistant";
  content: string;
}

/** Ask WealthPilot: ⌘J chat sheet over the portfolio's real numbers. */
export function ChatDrawer() {
  const open = useChatStore((s) => s.open);
  const setOpen = useChatStore((s) => s.setOpen);
  const consumeSeed = useChatStore((s) => s.consumeSeed);
  const toast = useToast();
  const close = useCallback(() => setOpen(false), [setOpen]);

  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const turnsRef = useRef<Turn[]>(turns);
  turnsRef.current = turns;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "j") {
        e.preventDefault();
        setOpen(!useChatStore.getState().open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  const [phase, setPhase] = useState<"idle" | "thinking" | "answering">("idle");
  const [followUps, setFollowUps] = useState<string[]>([]);
  const [health, setHealth] = useState<Awaited<ReturnType<typeof api.aiDataHealth>> | null>(null);
  const [speak, setSpeak] = useState(false);
  const [listening, setListening] = useState(false);
  const historyLoaded = useRef(false);

  // Phase 47: browser voice — mic dictation + spoken replies (no server model).
  /* eslint-disable @typescript-eslint/no-explicit-any */
  function startDictation() {
    const w = window as any;
    const SR = w.webkitSpeechRecognition ?? w.SpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.onresult = (e: any) => setInput(e.results[0][0].transcript as string);
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    setListening(true);
    rec.start();
  }
  /* eslint-enable @typescript-eslint/no-explicit-any */

  function sayReply(text: string) {
    if (!speak || typeof window === "undefined" || !window.speechSynthesis) return;
    const clean = text.split(/FOLLOW-UPS:/i)[0].replace(/\[\[chart:\w+\]\]/g, "").trim();
    if (!clean) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(clean.slice(0, 600)));
  }

  // Freshness check so Pilot flags stale data instead of sounding equally sure.
  useEffect(() => {
    if (!open) return;
    api.aiDataHealth().then(setHealth).catch(() => {});
  }, [open]);

  // Pilot remembers: preload recent exchanges once, on first open.
  useEffect(() => {
    if (!open || historyLoaded.current) return;
    historyLoaded.current = true;
    api
      .aiChatHistory(6)
      .then((h) => {
        if (h.length && turnsRef.current.length === 0) {
          setTurns(h.map((t) => ({ role: t.role, content: stripFollowUps(t.content).text })));
        }
      })
      .catch(() => {});
  }, [open]);

  async function send(message: string) {
    if (!message || busy) return;
    setInput("");
    const history = turnsRef.current;
    setTurns((t) => [...t, { role: "user", content: message }]);
    setBusy(true);
    setPhase("thinking");
    setFollowUps([]);
    try {
      // Stream first; fall back to the non-streaming endpoint on failure.
      const res = await fetch(`${API_BASE}/api/ai/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history, screen: useChatStore.getState().screen }),
      });
      if (!res.ok || !res.body) throw new Error("no stream");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let sse = "";
      let reply = "";
      let finalReply = "";
      let appended = false;
      let failed = false;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        sse += decoder.decode(value, { stream: true });
        const events = sse.split("\n\n");
        sse = events.pop() ?? "";
        for (const ev of events) {
          const kind = ev.match(/^event: (.+)$/m)?.[1];
          const data = (ev.match(/^data: (.*)$/m)?.[1] ?? "").replaceAll("\\n", "\n");
          if (kind === "phase" && data === "answering") setPhase("answering");
          else if (kind === "token") {
            reply += data;
            if (!appended) {
              appended = true;
              setTurns((t) => [...t, { role: "assistant", content: reply }]);
            } else {
              const snap = reply;
              setTurns((t) => [...t.slice(0, -1), { role: "assistant", content: snap }]);
            }
          } else if (kind === "final") finalReply = data;
          else if (kind === "error") failed = true;
        }
      }
      if (failed || !reply.trim()) throw new Error("stream empty");
      // Prefer the server's normalized reply (raw stream may carry a literal
      // FOLLOW-UPS placeholder from the fine-tuned model).
      const parsed = stripFollowUps(finalReply || reply);
      setFollowUps(parsed.followUps);
      setTurns((t) => [...t.slice(0, -1), { role: "assistant", content: parsed.text }]);
      sayReply(parsed.text);
    } catch {
      try {
        const res = await api.aiChat(message, history, useChatStore.getState().screen);
        setTurns((t) => [
          ...t.filter((x, i) => i < t.length - (t[t.length - 1]?.role === "assistant" ? 1 : 0)),
          {
            role: "assistant",
            content:
              res.status === "ok" && res.reply
                ? (() => {
                    const parsed = stripFollowUps(res.reply);
                    setFollowUps(parsed.followUps);
                    return parsed.text;
                  })()
                : "AI isn't configured yet — start Ollama on your 3070 and set OLLAMA_URL in .env, then restart the backend.",
          },
        ]);
      } catch {
        toast("Chat failed — the backend or model didn't respond. Try again.", "error");
      }
    } finally {
      setBusy(false);
      setPhase("idle");
    }
  }

  // Palette hand-off: when opened with a seeded question, ask it immediately.
  useEffect(() => {
    if (!open) return;
    const seed = consumeSeed();
    if (seed) void send(seed);
    requestAnimationFrame(() => inputRef.current?.focus());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns, busy]);

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        aria-label="Ask WealthPilot (⌘J)"
        onClick={() => setOpen(true)}
      >
        <MessageSquare aria-hidden="true" />
        <span className="hidden sm:inline">Ask</span>
        <kbd className="hidden rounded bg-muted px-1.5 py-0.5 text-2xs text-muted-foreground lg:inline">
          ⌘J
        </kbd>
      </Button>

      <Sheet open={open} onClose={close} label="Ask WealthPilot">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-[0.14em]">
              Pilot
            </h2>
            <p className="text-xs text-muted-foreground">
              Your portfolio copilot — answers use live numbers.
            </p>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              aria-label={speak ? "Mute spoken replies" : "Speak replies"}
              title={speak ? "Spoken replies on" : "Speak replies"}
              onClick={() => {
                if (speak) window.speechSynthesis?.cancel();
                setSpeak((s) => !s);
              }}
            >
              {speak ? <Volume2 aria-hidden="true" /> : <VolumeX aria-hidden="true" />}
            </Button>
            <Button variant="ghost" size="sm" aria-label="Close chat" onClick={() => setOpen(false)}>
              <X aria-hidden="true" />
            </Button>
          </div>
        </header>

        {health?.stale ? (
          <div className="flex items-start gap-2 border-b border-warning/30 bg-warning/[0.08] px-4 py-2 text-xs text-muted-foreground">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden="true" />
            <span>
              {health.reasons[0] ?? "Data may be stale."} Pilot answers with{" "}
              {health.confidence} confidence.
            </span>
          </div>
        ) : null}

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
          {turns.length === 0 && !busy ? (
            <p className="text-sm text-muted-foreground">
              Try: “why did my VaR change?” · “which stock is closest to the +10%
              sell threshold?” · “explain my diversification ratio”
            </p>
          ) : null}
          {turns.map((t, i) => (
            <div
              key={i}
              className={cn(
                "group/turn max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm leading-relaxed",
                t.role === "user" ? "ml-auto bg-primary/15 text-foreground" : "bg-muted",
              )}
            >
              {t.content.replace(CHART_RE, "").trim()}
              {t.role === "assistant"
                ? [...t.content.matchAll(CHART_RE)].map((m, ci) => (
                    <InlineChart key={ci} kind={m[1]} />
                  ))
                : null}
              {t.role === "assistant" ? (
                <button
                  type="button"
                  aria-label="Save to knowledge"
                  title="Save this answer into Pilot's knowledge base"
                  onClick={() => {
                    const q = turns[i - 1]?.content ?? "Pilot note";
                    void api
                      .saveKnowledge(q.slice(0, 80), t.content)
                      .then(() => toast("Saved to knowledge — Pilot will remember this.", "success"))
                      .catch(() => toast("Couldn't save the note.", "error"));
                  }}
                  className="ml-2 inline-flex size-5 items-center justify-center rounded align-text-bottom text-muted-foreground opacity-0 transition-opacity hover:bg-background hover:text-primary group-hover/turn:opacity-100 focus-visible:opacity-100"
                >
                  <BookmarkPlus className="size-3.5" aria-hidden="true" />
                </button>
              ) : null}
            </div>
          ))}
          {busy && phase !== "answering" ? (
            <div className="w-fit rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <span className="size-1.5 animate-pulse rounded-full bg-primary motion-reduce:animate-none" />
                Reasoning… (local model — can take a minute)
              </span>
            </div>
          ) : null}
          {!busy && followUps.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {followUps.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => void send(q)}
                  className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                >
                  {q}
                </button>
              ))}
            </div>
          ) : null}
          <div ref={endRef} />
        </div>

        <form
          className="flex gap-2 border-t border-border p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void send(input.trim());
          }}
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your portfolio…"
            aria-label="Message"
            className="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            aria-label="Dictate"
            title="Speak your question"
            onClick={startDictation}
            className={listening ? "text-loss" : ""}
          >
            <Mic aria-hidden="true" />
          </Button>
          <Button type="submit" size="sm" disabled={busy || !input.trim()} aria-label="Send">
            <Send aria-hidden="true" />
          </Button>
        </form>
      </Sheet>
    </>
  );
}
