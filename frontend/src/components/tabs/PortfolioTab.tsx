"use client";

import * as React from "react";
import dynamic from "next/dynamic";

import { HoldingsTab } from "@/components/tabs/HoldingsTab";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Snapshot } from "@/lib/types";

// Funds (MF audit) and Trends (history + projection) are the two heaviest tabs
// (chart deps), so they stay lazy — now loaded on first activation of their
// segment rather than as separate top-level tabs.
const subSkeleton = () => <Skeleton className="h-72 w-full rounded-xl" />;
const FundsTab = dynamic(
  () => import("@/components/tabs/FundsTab").then((m) => m.FundsTab),
  { loading: subSkeleton },
);
const TrendsTab = dynamic(
  () => import("@/components/tabs/TrendsTab").then((m) => m.TrendsTab),
  { loading: subSkeleton },
);

// Old top-level hashes (#holdings/#funds/#trends) now alias into this one tab's
// three segments — so deep links and the Issues "Fix" routing (→ #funds) keep
// working after the merge.
const SEGMENTS = ["holdings", "funds", "trends"] as const;
type Segment = (typeof SEGMENTS)[number];
const SEG_LABEL: Record<Segment, string> = {
  holdings: "Holdings",
  funds: "Funds",
  trends: "Trends",
};

function segFromHash(): Segment | null {
  if (typeof window === "undefined") return null;
  const h = window.location.hash.slice(1);
  if ((SEGMENTS as readonly string[]).includes(h)) return h as Segment;
  if (h === "portfolio") return "holdings";
  return null;
}

/**
 * Portfolio — the merged home for everything you hold. Consolidates what used
 * to be three separate top-level tabs (Holdings, Funds, Trends) behind one
 * segmented sub-nav, cutting the Monitor group's tab count and putting
 * positions, the fund audit, and the value-over-time history in one place.
 */
export function PortfolioTab({ snapshot }: { snapshot: Snapshot }) {
  const [seg, setSeg] = React.useState<Segment>(() => segFromHash() ?? "holdings");

  // An external jump to #funds/#trends (e.g. the Issues "Fix" links) fires a
  // hashchange while this tab is kept alive — follow it to the right segment.
  React.useEffect(() => {
    const onHash = () => {
      const s = segFromHash();
      if (s) setSeg(s);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const change = (v: string) => {
    const next = v as Segment;
    setSeg(next);
    // Reflect the segment in the hash (without a history entry) so it stays
    // deep-linkable and the parent tab stays on Portfolio.
    if (window.location.hash.slice(1) !== next) {
      window.history.replaceState(null, "", `#${next}`);
    }
  };

  return (
    <Tabs value={seg} onValueChange={change} className="space-y-4">
      <TabsList className="w-full sm:w-auto">
        {SEGMENTS.map((s) => (
          <TabsTrigger key={s} value={s} className="flex-1 sm:flex-none">
            {SEG_LABEL[s]}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="holdings">
        <HoldingsTab snapshot={snapshot} />
      </TabsContent>
      <TabsContent value="funds">
        <FundsTab />
      </TabsContent>
      <TabsContent value="trends">
        <TrendsTab />
      </TabsContent>
    </Tabs>
  );
}
