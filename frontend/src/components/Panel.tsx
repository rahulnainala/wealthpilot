import * as React from "react";

import { cn } from "@/lib/utils";

interface Props {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  children: React.ReactNode;
}

export function Panel({
  title,
  description,
  action,
  className,
  bodyClassName,
  children,
}: Props) {
  return (
    <section
      className={cn(
        "rounded-xl border border-border bg-card text-card-foreground shadow-sm",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-border px-5 py-3">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em]">{title}</h2>
          {description ? (
            <p className="text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {action}
      </header>
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  );
}
