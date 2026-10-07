"use client";

import { AlertTriangle } from "lucide-react";

export function ReconnectBanner({ loginUrl }: { loginUrl: string }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm text-warning"
    >
      <AlertTriangle className="size-4 shrink-0" />
      <span>Your Zerodha session has expired.</span>
      <a
        href={loginUrl}
        target="_blank"
        rel="noreferrer"
        className="font-semibold underline underline-offset-2"
      >
        Reconnect Zerodha
      </a>
    </div>
  );
}
