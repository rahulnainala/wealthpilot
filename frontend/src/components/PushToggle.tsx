"use client";

import { useEffect, useState } from "react";
import { Bell, BellOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type PushState = "unknown" | "unsupported" | "off" | "on" | "denied";

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(normalized);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

/** Enable browser push so Phase-7 action alerts reach you with the app closed. */
export function PushToggle() {
  const [state, setState] = useState<PushState>("unknown");

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !("serviceWorker" in navigator) ||
      !("PushManager" in window) ||
      !("Notification" in window)
    ) {
      setState("unsupported");
      return;
    }
    navigator.serviceWorker.register("/sw.js").catch(() => {});
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) =>
        setState(Notification.permission === "denied" ? "denied" : sub ? "on" : "off"),
      )
      .catch(() => setState("off"));
  }, []);

  async function enable() {
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") {
        setState("denied");
        return;
      }
      const { key } = await api.aiVapidKey();
      if (!key) {
        setState("off"); // server has no VAPID keys configured
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      });
      const json = sub.toJSON();
      await api.aiSubscribe({
        endpoint: json.endpoint ?? "",
        keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
      });
      setState("on");
    } catch {
      setState("off");
    }
  }

  if (state === "unknown" || state === "unsupported") return null;

  const label =
    state === "on" ? "Alerts on" : state === "denied" ? "Alerts blocked" : "Enable alerts";
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => void enable()}
      disabled={state === "on" || state === "denied"}
      aria-label={label}
    >
      {state === "on" ? <Bell aria-hidden="true" /> : <BellOff aria-hidden="true" />}
      <span className="hidden sm:inline">{label}</span>
    </Button>
  );
}
