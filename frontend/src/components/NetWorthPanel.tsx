"use client";

import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";

import { Panel } from "@/components/Panel";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";

type Asset = { id: number; name: string; category: string; value: number };
const CATEGORIES = ["bank", "epf", "real_estate", "gold", "insurance", "other"];

/** Phase 49: net worth = Zerodha portfolio + manual external assets. */
export function NetWorthPanel() {
  const [nw, setNw] = useState<Awaited<ReturnType<typeof api.netWorth>> | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("bank");
  const [value, setValue] = useState("");

  async function refresh() {
    setNw(await api.netWorth().catch(() => null));
    setAssets(await api.listAssets().catch(() => []));
  }
  useEffect(() => {
    void refresh();
  }, []);

  async function add() {
    const v = Number(value);
    if (!name.trim() || !v) return;
    await api.addAsset({ name: name.trim(), category, value: v });
    setName("");
    setValue("");
    void refresh();
  }

  const input =
    "min-w-0 rounded-lg border border-input bg-background px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

  return (
    <Panel title="Net Worth" description="Zerodha portfolio + your other assets.">
      {nw ? (
        <div className="mb-3 flex items-baseline gap-3">
          <span className="text-2xl font-semibold tabular-nums">{inr(nw.net_worth)}</span>
          <span className="text-xs text-muted-foreground tabular-nums">
            portfolio {inr(nw.portfolio)} + external {inr(nw.external)}
          </span>
        </div>
      ) : null}

      <ul className="space-y-1.5">
        {assets.map((a) => (
          <li key={a.id} className="flex items-center justify-between text-sm">
            <span>
              {a.name} <span className="text-2xs uppercase text-muted-foreground">{a.category}</span>
            </span>
            <span className="flex items-center gap-2 tabular-nums">
              {inr(a.value)}
              <button
                type="button"
                aria-label={`Delete ${a.name}`}
                onClick={() => api.deleteAsset(a.id).then(refresh)}
                className="text-muted-foreground hover:text-loss"
              >
                <Trash2 className="size-3.5" aria-hidden="true" />
              </button>
            </span>
          </li>
        ))}
      </ul>

      <form
        className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <input className={`${input} basis-full sm:basis-0 sm:flex-1`} placeholder="Asset (e.g. HDFC savings)" value={name} onChange={(e) => setName(e.target.value)} aria-label="Asset name" />
        <select className={`${input} flex-1 sm:flex-none`} value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.replace("_", " ")}</option>
          ))}
        </select>
        <input className={`${input} w-24 sm:w-28`} type="number" placeholder="Value" value={value} onChange={(e) => setValue(e.target.value)} aria-label="Value" />
        <Button type="submit" size="sm" disabled={!name.trim() || !Number(value)}>Add</Button>
      </form>
    </Panel>
  );
}
