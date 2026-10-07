"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { CornerDownLeft, Search } from "lucide-react";

import { cn } from "@/lib/utils";

export interface CommandAction {
  id: string;
  label: string;
  hint?: string;
  group: string;
  run: (query: string) => void;
}

/** ⌘K command palette: filterable actions with arrow-key navigation. */
export function CommandPalette({
  open,
  onClose,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  actions: CommandAction[];
}) {
  const [query, setQuery] = React.useState("");
  const [index, setIndex] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    const hits = q
      ? actions.filter((a) => a.label.toLowerCase().includes(q))
      : actions;
    // "Ask" is always available as the escape hatch for free-text questions.
    return hits.length > 0 ? hits : actions.filter((a) => a.id === "ask-ai");
  }, [actions, query]);

  React.useEffect(() => {
    if (open) {
      setQuery("");
      setIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  React.useEffect(() => setIndex(0), [query]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setIndex((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndex((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" && filtered[index]) {
      e.preventDefault();
      onClose();
      filtered[index].run(query);
    }
  };

  let lastGroup = "";
  return createPortal(
    <div className="fixed inset-0 z-50" onKeyDown={onKeyDown}>
      <div
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 bg-background/60 backdrop-blur-[2px] animate-in fade-in duration-150 motion-reduce:animate-none"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="absolute left-1/2 top-24 w-full max-w-lg -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-popover shadow-xl animate-in fade-in zoom-in-95 duration-150 motion-reduce:animate-none"
      >
        <div className="flex items-center gap-2.5 border-b border-border px-4 py-3">
          <Search className="size-4 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to a page, holding — or ask anything…"
            aria-label="Command"
            role="combobox"
            aria-expanded="true"
            aria-controls="wp-command-results"
            aria-activedescendant={filtered[index] ? `wp-cmd-${filtered[index].id}` : undefined}
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="rounded bg-muted px-1.5 py-0.5 text-2xs text-muted-foreground">esc</kbd>
        </div>
        <ul role="listbox" id="wp-command-results" aria-label="Results" className="max-h-80 overflow-y-auto p-2">
          {filtered.map((a, i) => {
            const header = a.group !== lastGroup ? a.group : null;
            lastGroup = a.group;
            return (
              <React.Fragment key={a.id}>
                {header ? (
                  <li
                    aria-hidden="true"
                    className="px-2 pb-1 pt-2 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground/70"
                  >
                    {header}
                  </li>
                ) : null}
                <li
                  role="option"
                  id={`wp-cmd-${a.id}`}
                  aria-selected={i === index}
                  onMouseEnter={() => setIndex(i)}
                  onClick={() => {
                    onClose();
                    a.run(query);
                  }}
                  className={cn(
                    "flex cursor-pointer items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-sm",
                    i === index ? "bg-primary/15 text-primary" : "text-foreground",
                  )}
                >
                  <span className="min-w-0 truncate">{a.label}</span>
                  <span className="flex shrink-0 items-center gap-2 text-2xs text-muted-foreground">
                    {a.hint}
                    {i === index ? <CornerDownLeft className="size-3" aria-hidden="true" /> : null}
                  </span>
                </li>
              </React.Fragment>
            );
          })}
        </ul>
      </div>
    </div>,
    document.body,
  );
}
