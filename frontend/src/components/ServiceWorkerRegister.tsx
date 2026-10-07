"use client";

import { useEffect } from "react";

/** Registers the PWA service worker app-wide (install support + push delivery). */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof navigator !== "undefined" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return null;
}
