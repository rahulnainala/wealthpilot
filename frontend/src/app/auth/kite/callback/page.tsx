"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { API_BASE } from "@/lib/config";

type Status = "working" | "ok" | "error";

export default function KiteCallbackPage() {
  const [status, setStatus] = useState<Status>("working");
  const [message, setMessage] = useState("Connecting your Zerodha account…");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestToken = params.get("request_token");
    const kiteStatus = params.get("status");

    if (!requestToken || kiteStatus === "cancelled") {
      setStatus("error");
      setMessage("Login was cancelled or no request token was returned by Zerodha.");
      return;
    }

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/auth/kite/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_token: requestToken }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? body.message ?? res.statusText);
        }
        const body = await res.json();
        setStatus("ok");
        setMessage(`Connected as ${body.user_id}. Redirecting to your dashboard…`);
        setTimeout(() => {
          window.location.href = "/";
        }, 1600);
      } catch (err) {
        setStatus("error");
        setMessage(`Could not connect: ${(err as Error).message}`);
      }
    })();
  }, []);

  const Icon =
    status === "working" ? Loader2 : status === "ok" ? CheckCircle2 : XCircle;
  const color =
    status === "working"
      ? "text-muted-foreground"
      : status === "ok"
        ? "text-emerald-600"
        : "text-rose-600";

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-xl border border-border bg-card p-8 text-center shadow-sm">
        <Icon
          className={`mx-auto mb-4 size-10 ${color} ${
            status === "working" ? "animate-spin" : ""
          }`}
        />
        <h1 className="text-lg font-semibold">Zerodha Connect</h1>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        {status === "error" ? (
          <Link
            href="/"
            className="mt-4 inline-block text-sm font-medium text-primary underline underline-offset-2"
          >
            Back to dashboard
          </Link>
        ) : null}
      </div>
    </div>
  );
}
