"use client";

import { Sparkles } from "lucide-react";

import { Tooltip } from "@/components/ui/tooltip";
import { useChatStore } from "@/store/useChatStore";

/** One-tap seeded AI question — opens the ⌘J chat and asks immediately. */
export function AskAI({
  question,
  tip = "Ask WealthPilot",
  className,
}: {
  question: string;
  tip?: string;
  className?: string;
}) {
  const ask = useChatStore((s) => s.ask);
  return (
    <Tooltip label={tip} side="top" className={className}>
      <button
        type="button"
        aria-label={tip}
        onClick={() => ask(question)}
        className="flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-primary/15 hover:text-primary"
      >
        <Sparkles className="size-3.5" aria-hidden="true" />
      </button>
    </Tooltip>
  );
}
