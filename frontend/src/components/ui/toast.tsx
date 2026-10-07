"use client";

import * as React from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

interface Toast {
  id: number;
  message: string;
  tone: "default" | "success" | "error";
}

const ToastContext = React.createContext<(message: string, tone?: Toast["tone"]) => void>(
  () => {},
);

export function useToast() {
  return React.useContext(ToastContext);
}

const TONE_CLASS: Record<Toast["tone"], string> = {
  default: "border-border",
  success: "border-gain/40",
  error: "border-loss/40",
};

const DOT_CLASS: Record<Toast["tone"], string> = {
  default: "bg-muted-foreground",
  success: "bg-gain",
  error: "bg-loss",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const push = React.useCallback((message: string, tone: Toast["tone"] = "default") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      {mounted
        ? createPortal(
            <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2">
              {toasts.map((t) => (
                <div
                  key={t.id}
                  role="status"
                  className={cn(
                    "pointer-events-auto flex items-center gap-2.5 rounded-lg border bg-popover px-3.5 py-2.5 text-sm shadow-lg",
                    "animate-in slide-in-from-bottom-2 fade-in duration-200 motion-reduce:animate-none",
                    TONE_CLASS[t.tone],
                  )}
                >
                  <span className={cn("size-1.5 shrink-0 rounded-full", DOT_CLASS[t.tone])} />
                  {t.message}
                </div>
              ))}
            </div>,
            document.body,
          )
        : null}
    </ToastContext.Provider>
  );
}
