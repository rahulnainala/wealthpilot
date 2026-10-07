import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

import { ServiceWorkerRegister } from "@/components/ServiceWorkerRegister";
import { ToastProvider } from "@/components/ui/toast";
import { DEMO_MODE } from "@/lib/config";

const plexSans = IBM_Plex_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "WealthPilot — Portfolio Analytics & Goal Tracker",
  description:
    "Personal Zerodha portfolio audit, live market data, and goal simulations.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "WealthPilot", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#0a0e14",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${plexSans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <ServiceWorkerRegister />
        {DEMO_MODE && (
          <p
            role="note"
            className="border-b border-warning/40 bg-warning/[0.08] px-4 py-2 text-center text-xs text-foreground"
          >
            <span className="font-semibold text-warning">Demo</span> · a fictional portfolio, read-only.
            Editing, uploads and AI chat are turned off.
          </p>
        )}
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
