"use client";

import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";

import { Panel } from "@/components/Panel";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { pct, signColor } from "@/lib/format";

type Item = { id: number; symbol: string; last_price: number | null; change_pct: number | null };

/** Phase 50: a live-quote watchlist + gap-based screener ideas. */
export function WatchlistPanel() {
  const [items, setItems] = useState<Item[]>([]);
  const [ideas, setIdeas] = useState<string[]>([]);
  const [symbol, setSymbol] = useState("");

  async function refresh() {
    setItems(await api.watchlist().catch(() => []));
  }
  useEffect(() => {
    void refresh();
    api.screener().then((r) => setIdeas(r.ideas)).catch(() => {});
  }, []);

  async function add() {
    if (!symbol.trim()) return;
    await api.addWatch(symbol.trim());
    setSymbol("");
    void refresh();
  }

  return (
    <Panel title="Watchlist" description="Track candidates + strategy-gap ideas.">
      {ideas.length > 0 ? (
        <ul className="mb-3 space-y-1">
          {ideas.map((t, i) => (
            <li key={i} className="text-xs text-muted-foreground">• {t}</li>
          ))}
        </ul>
      ) : null}
      <ul className="space-y-1.5">
        {items.map((it) => (
          <li key={it.id} className="flex items-center justify-between text-sm tabular-nums">
            <span className="font-medium">{it.symbol}</span>
            <span className="flex items-center gap-3">
              {it.last_price != null ? (
                <>
                  <span>{it.last_price.toLocaleString("en-IN")}</span>
                  {it.change_pct != null ? (
                    <span className={signColor(it.change_pct)}>{pct(it.change_pct)}</span>
                  ) : null}
                </>
              ) : (
                <span className="text-2xs text-muted-foreground">no quote</span>
              )}
              <button
                type="button"
                aria-label={`Remove ${it.symbol}`}
                onClick={() => api.deleteWatch(it.id).then(refresh)}
                className="text-muted-foreground hover:text-loss"
              >
                <Trash2 className="size-3.5" aria-hidden="true" />
              </button>
            </span>
          </li>
        ))}
      </ul>
      <form
        className="mt-3 flex gap-2 border-t border-border pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="Add symbol (e.g. TATAPOWER)"
          aria-label="Symbol"
          className="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
        />
        <Button type="submit" size="sm" disabled={!symbol.trim()}>Add</Button>
      </form>
    </Panel>
  );
}
