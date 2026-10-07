"use client";

import { useEffect, useState } from "react";
import { Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { appAuth } from "@/lib/api";

/** Phase 40: gate the app behind login when the backend has APP_PASSWORD set. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function check() {
    try {
      const { auth_enabled } = await appAuth.config();
      if (!auth_enabled) {
        setAuthed(true);
        return;
      }
      await appAuth.me(); // 401 if token missing/expired
      setAuthed(true);
    } catch {
      setAuthed(false);
    } finally {
      setReady(true);
    }
  }

  useEffect(() => {
    void check();
    const onExpired = () => setAuthed(false);
    window.addEventListener("wp:auth-required", onExpired);
    return () => window.removeEventListener("wp:auth-required", onExpired);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { token } = await appAuth.login(password);
      localStorage.setItem("wp:token", token);
      setPassword("");
      setAuthed(true);
    } catch {
      setError("Incorrect password.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) return null;
  if (authed) return <>{children}</>;

  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-border bg-card p-6 shadow-sm"
      >
        <div className="flex items-center gap-2">
          <Lock className="size-5 text-primary" aria-hidden="true" />
          <h1 className="text-lg font-semibold">WealthPilot</h1>
        </div>
        <p className="text-sm text-muted-foreground">Enter your password to continue.</p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          aria-label="Password"
          className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
        />
        {error ? <p className="text-sm text-loss">{error}</p> : null}
        <Button type="submit" className="w-full" disabled={busy || !password}>
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}
