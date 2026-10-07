"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertTriangle,
  BrainCircuit,
  Briefcase,
  GraduationCap,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldAlert,
  BarChart3,
  LayoutDashboard,
  ListChecks,
  NotebookPen,
  PiggyBank,
  Navigation,
  PieChart,
  RefreshCw,
  Target,
} from "lucide-react";

import { ChatDrawer } from "@/components/ChatDrawer";
import { useEngineHealth } from "@/components/StatusBadge";
import { CommandPalette, type CommandAction } from "@/components/ui/command";
import { useToast } from "@/components/ui/toast";
import { Tooltip } from "@/components/ui/tooltip";
import { useChatStore } from "@/store/useChatStore";
import { useTickerStore } from "@/store/useTickerStore";
import { Loadable } from "@/components/Loadable";
import { ReconnectBanner } from "@/components/ReconnectBanner";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import { StatusBadge } from "@/components/StatusBadge";
import { OverviewTab } from "@/components/tabs/OverviewTab";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi } from "@/hooks/useApi";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useTicks } from "@/hooks/useTicks";
import { ApiError, api } from "@/lib/api";
import type { Issue, Snapshot } from "@/lib/types";
import { cn } from "@/lib/utils";

// Overview is the default tab and stays in the main bundle; every other tab
// (and its chart dependencies) loads on first activation.
const tabSkeleton = () => <Skeleton className="h-64 w-full rounded-xl" />;
const PortfolioTab = dynamic(
  () => import("@/components/tabs/PortfolioTab").then((m) => m.PortfolioTab),
  { loading: tabSkeleton },
);
const RiskTab = dynamic(
  () => import("@/components/tabs/RiskTab").then((m) => m.RiskTab),
  { loading: tabSkeleton },
);
const LearnTab = dynamic(
  () => import("@/components/tabs/LearnTab").then((m) => m.LearnTab),
  { loading: tabSkeleton },
);
const AiTab = dynamic(
  () => import("@/components/tabs/AiTab").then((m) => m.AiTab),
  { loading: tabSkeleton },
);
const MarketTab = dynamic(
  () => import("@/components/tabs/MarketTab").then((m) => m.MarketTab),
  { loading: tabSkeleton },
);
const GoalsTab = dynamic(
  () => import("@/components/tabs/GoalsTab").then((m) => m.GoalsTab),
  { loading: tabSkeleton },
);
const BasketTab = dynamic(
  () => import("@/components/tabs/BasketTab").then((m) => m.BasketTab),
  { loading: tabSkeleton },
);
const IssuesTab = dynamic(
  () => import("@/components/tabs/IssuesTab").then((m) => m.IssuesTab),
  { loading: tabSkeleton },
);
const ActionPlanTab = dynamic(
  () => import("@/components/tabs/ActionPlanTab").then((m) => m.ActionPlanTab),
  { loading: tabSkeleton },
);
const RetirementTab = dynamic(
  () => import("@/components/tabs/RetirementTab").then((m) => m.RetirementTab),
  { loading: tabSkeleton },
);
const JournalTab = dynamic(
  () => import("@/components/tabs/JournalTab").then((m) => m.JournalTab),
  { loading: tabSkeleton },
);

const TABS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, group: "Monitor" },
  { id: "portfolio", label: "Portfolio", icon: Briefcase, group: "Monitor" },
  { id: "risk", label: "Risk", icon: ShieldAlert, group: "Monitor" },
  { id: "market", label: "Market", icon: BarChart3, group: "Monitor" },
  { id: "goals", label: "Goals", icon: Target, group: "Plan" },
  { id: "retirement", label: "Retirement", icon: PiggyBank, group: "Plan" },
  { id: "basket", label: "Basket", icon: PieChart, group: "Plan" },
  { id: "action-plan", label: "Action Plan", icon: ListChecks, group: "Plan" },
  { id: "issues", label: "Issues", icon: AlertTriangle, group: "Audit" },
  { id: "ai", label: "AI", icon: BrainCircuit, group: "System" },
  { id: "journal", label: "Journal", icon: NotebookPen, group: "System" },
  { id: "learn", label: "Learn", icon: GraduationCap, group: "System" },
];

const GROUPS = ["Monitor", "Plan", "Audit", "System"];

// Holdings, Funds and Trends were merged into the Portfolio tab's three
// segments — keep their old hashes working as aliases so deep links and the
// Issues "Fix" routing (→ #funds) still land in the right place.
const HASH_ALIAS: Record<string, string> = {
  holdings: "portfolio",
  funds: "portfolio",
  trends: "portfolio",
};

// Matches HoldingsTab's shape (page header, holdings table, MF table, then the
// two-up X-ray / net-worth panels) so the tab doesn't reflow when data lands.
function HoldingsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-16 rounded-xl" />
      <Skeleton className="h-72 rounded-xl" />
      <Skeleton className="h-56 rounded-xl" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    </div>
  );
}

function OverviewSkeleton() {
  // Mirrors the redesigned Overview so nothing shifts or re-corners on swap:
  // account hero, needs-attention band, instruments strip, two-up allocation —
  // each block rounded-xl to match the card it becomes (Skeleton defaults to
  // rounded-md).
  return (
    <div className="space-y-4">
      <Skeleton className="h-40 rounded-xl" />
      <Skeleton className="h-11 rounded-xl" />
      <Skeleton className="h-20 rounded-xl" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
    </div>
  );
}

const isTabId = (id: string) => TABS.some((t) => t.id === id);
// Resolve a raw hash to a real tab id, following the Portfolio aliases.
const resolveTab = (hash: string): string | null => {
  const id = HASH_ALIAS[hash] ?? hash;
  return isTabId(id) ? id : null;
};

export function Dashboard() {
  useTicks();
  const [tab, setTab] = useState("overview");
  const [refreshing, setRefreshing] = useState(false);
  const [reconnectUrl, setReconnectUrl] = useState<string | null>(null);
  const navRef = useRef<HTMLElement>(null);
  const toast = useToast();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const streamStatus = useTickerStore((st) => st.streamStatus);
  const engine = useEngineHealth();

  // Open-issue count for the persistent nav badge — the one attention signal
  // that follows you across every screen, not just the Issues tab.
  const issues = useApi<Issue[]>(() => api.issues(), []);
  const issueCount = issues.data?.length ?? 0;
  const criticalCount = (issues.data ?? []).filter((i) => i.severity === "critical").length;

  useEffect(() => {
    setRailCollapsed(localStorage.getItem("wp:rail") === "collapsed");
  }, []);
  const toggleRail = () => {
    setRailCollapsed((c) => {
      localStorage.setItem("wp:rail", c ? "expanded" : "collapsed");
      return !c;
    });
  };

  // Palette owns ⌘K (chat moved to ⌘J).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Tab ↔ URL hash: deep links and refreshes land on the right section, and
  // browser back/forward walks tab history.
  useEffect(() => {
    const fromHash = resolveTab(window.location.hash.slice(1));
    if (fromHash) {
      setTab(fromHash);
      useChatStore.getState().setScreen(TABS.find((t) => t.id === fromHash)?.label ?? fromHash);
    }
    const onHashChange = () => {
      const next = resolveTab(window.location.hash.slice(1));
      if (next) setTab(next);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const selectTab = (id: string) => {
    const resolved = HASH_ALIAS[id] ?? id;
    setTab(resolved);
    useChatStore.getState().setScreen(TABS.find((t) => t.id === resolved)?.label ?? resolved);
    if (window.location.hash.slice(1) !== id) {
      window.history.pushState(null, "", `#${id}`);
    }
  };

  // Keep the active tab visible in the horizontally scrolling mobile strip —
  // on tab change and when the viewport crosses into the mobile layout. Guarded
  // to the narrow layout: on desktop the rail is a vertical sticky column, and
  // scrollIntoView there scrolls the whole window (tucking the page under the
  // sticky header) instead of the strip.
  const narrowNav = useMediaQuery("(max-width: 767px)");
  useEffect(() => {
    if (!narrowNav) return;
    navRef.current
      ?.querySelector('[data-state="active"]')
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [tab, narrowNav]);

  const snap = useApi<Snapshot>(async () => {
    try {
      return await api.latestSnapshot();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        return await api.refreshSnapshot();
      }
      throw err;
    }
  }, []);

  useEffect(() => {
    const err = snap.error;
    if (err instanceof ApiError && err.loginUrl) setReconnectUrl(err.loginUrl);
  }, [snap.error]);

  async function refresh() {
    setRefreshing(true);
    try {
      await api.refreshSnapshot();
      setReconnectUrl(null);
      await snap.reload();
      toast("Snapshot refreshed — holdings and analytics are current.", "success");
    } catch (err) {
      if (err instanceof ApiError && err.loginUrl) setReconnectUrl(err.loginUrl);
      else toast("Refresh failed — check the backend and try again.", "error");
    } finally {
      setRefreshing(false);
    }
  }

  const paletteActions: CommandAction[] = [
    ...TABS.map((t) => ({
      id: `tab-${t.id}`,
      label: t.label,
      hint: t.group,
      group: "Go to",
      run: () => selectTab(t.id),
    })),
    ...(snap.data?.holdings ?? [])
      .filter((h) => h.type === "stock")
      .map((h) => ({
        id: `sym-${h.symbol}`,
        label: h.symbol,
        hint: "holding",
        group: "Holdings",
        run: () => selectTab("holdings"),
      })),
    {
      id: "ask-ai",
      label: "Ask WealthPilot…",
      hint: "⌘J",
      group: "AI",
      run: (query: string) => useChatStore.getState().ask(query),
    },
  ];

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2.5">
            {/* Brand mark: a within-accent cyan gradient — one accent, no stray hue. */}
            <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-cyan-600 text-primary-foreground shadow-sm ring-1 ring-inset ring-white/10">
              <Navigation className="size-5" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-base font-bold leading-tight tracking-tight">
                WealthPilot
              </h1>
              <p className="text-xs text-muted-foreground">
                Portfolio audit &amp; goal tracker
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge snapshotTs={snap.data?.ts} />
            <ChatDrawer />
            <Button
              onClick={refresh}
              disabled={refreshing}
              variant="outline"
              size="sm"
              aria-label="Refresh"
            >
              <RefreshCw
                aria-hidden="true"
                className={refreshing ? "animate-spin motion-reduce:animate-none" : ""}
              />
              <span className="hidden sm:inline">Refresh</span>
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {reconnectUrl ? (
          <div className="mb-4">
            <ReconnectBanner loginUrl={reconnectUrl} />
          </div>
        ) : null}

        <div className="mb-4 empty:mb-0">
          <StaleDataBanner />
        </div>

        <Tabs
          value={tab}
          onValueChange={selectTab}
          className="flex flex-col gap-6 md:flex-row"
        >
          <aside className={railCollapsed ? "md:w-14 md:shrink-0" : "md:w-52 md:shrink-0"}>
            <nav aria-label="Sections" ref={navRef} className="md:sticky md:top-20 md:flex md:h-[calc(100vh-6.5rem)] md:flex-col">
              <button
                type="button"
                onClick={toggleRail}
                aria-label={railCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                className="mb-2 hidden size-8 items-center justify-center self-end rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground md:flex"
              >
                {railCollapsed ? (
                  <PanelLeftOpen className="size-4" aria-hidden="true" />
                ) : (
                  <PanelLeftClose className="size-4" aria-hidden="true" />
                )}
              </button>
              <TabsList className="flex-nowrap gap-1 overflow-x-auto rounded-none bg-transparent p-0 pb-1 md:flex-col md:items-stretch md:overflow-visible md:pb-0">
                {GROUPS.map((group, gi) => (
                  <div key={group} className="contents md:block">
                    {railCollapsed ? (
                      gi > 0 ? (
                        <div aria-hidden="true" className="mx-2 my-2 hidden border-t border-border md:block" />
                      ) : null
                    ) : (
                      <div
                        aria-hidden="true"
                        className={cn(
                          "hidden px-3 pb-1 text-2xs font-semibold uppercase tracking-[0.14em] text-muted-foreground/70 md:block",
                          gi > 0 && "pt-4",
                        )}
                      >
                        {group}
                      </div>
                    )}
                    {TABS.filter((t) => t.group === group).map(({ id, label, icon: Icon }) => {
                      const trigger = (
                        <TabsTrigger
                          key={id}
                          value={id}
                          className={cn(
                            "relative w-full shrink-0 justify-start gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors data-[state=active]:bg-primary/15 data-[state=active]:text-primary data-[state=active]:shadow-none data-[state=inactive]:text-muted-foreground data-[state=inactive]:hover:bg-muted data-[state=inactive]:hover:text-foreground",
                            "data-[state=active]:before:absolute data-[state=active]:before:inset-y-2 data-[state=active]:before:left-0 data-[state=active]:before:hidden data-[state=active]:before:w-0.5 data-[state=active]:before:rounded-full data-[state=active]:before:bg-primary md:data-[state=active]:before:block",
                            railCollapsed && "md:justify-center md:px-0",
                          )}
                        >
                          <Icon className="size-4 shrink-0" aria-hidden="true" />
                          <span className={railCollapsed ? "md:hidden" : undefined}>{label}</span>
                          {id === "issues" && issueCount > 0 ? (
                            <>
                              {/* Count pill — shows in the expanded rail and in the
                                  mobile strip; hidden when the desktop rail collapses. */}
                              <span
                                className={cn(
                                  "ml-auto inline-flex min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-2xs font-semibold leading-5 tabular-nums",
                                  criticalCount > 0 ? "bg-loss/15 text-loss" : "bg-warning/15 text-warning",
                                  railCollapsed && "md:hidden",
                                )}
                                aria-label={`${issueCount} open ${issueCount === 1 ? "issue" : "issues"}`}
                              >
                                {issueCount}
                              </span>
                              {/* Collapsed desktop rail: a dot on the icon corner. */}
                              {railCollapsed ? (
                                <span
                                  className={cn(
                                    "absolute right-1.5 top-1.5 hidden size-1.5 rounded-full md:block",
                                    criticalCount > 0 ? "bg-loss" : "bg-warning",
                                  )}
                                  aria-hidden="true"
                                />
                              ) : null}
                            </>
                          ) : null}
                        </TabsTrigger>
                      );
                      return railCollapsed ? (
                        <Tooltip key={id} label={label} className="w-full">
                          {trigger}
                        </Tooltip>
                      ) : (
                        trigger
                      );
                    })}
                  </div>
                ))}
              </TabsList>
              <div
                className={cn(
                  "mt-auto hidden items-center gap-2 border-t border-border px-3 py-3 md:flex",
                  railCollapsed && "md:justify-center md:px-0",
                )}
              >
                <Tooltip label={`Data stream: ${streamStatus}`} side="top">
                  <span
                    className={cn(
                      "size-1.5 rounded-full",
                      streamStatus === "live" ? "bg-gain" : streamStatus === "delayed" ? "bg-warning" : "bg-muted-foreground/60",
                    )}
                  />
                </Tooltip>
                <Tooltip label={`Risk engine: ${engine}`} side="top">
                  <span
                    className={cn(
                      "size-1.5 rounded-full",
                      engine === "ok" ? "bg-gain" : engine === "down" ? "bg-loss" : "bg-muted-foreground/60",
                    )}
                  />
                </Tooltip>
                {!railCollapsed ? (
                  <span className="text-2xs uppercase tracking-[0.14em] text-muted-foreground">
                    Systems
                  </span>
                ) : null}
              </div>
            </nav>
          </aside>

          <main className="min-w-0 flex-1">
            <TabsContent value="overview" className="mt-0">
              <Loadable state={snap} skeleton={<OverviewSkeleton />}>
                {(data) => <OverviewTab snapshot={data} />}
              </Loadable>
            </TabsContent>
            <TabsContent value="portfolio" className="mt-0">
              <Loadable
                state={snap}
                skeleton={
                  <div className="space-y-4">
                    <Skeleton className="h-9 w-full rounded-lg sm:w-72" />
                    <HoldingsSkeleton />
                  </div>
                }
              >
                {(data) => <PortfolioTab snapshot={data} />}
              </Loadable>
            </TabsContent>
            <TabsContent value="risk" className="mt-0">
              <RiskTab />
            </TabsContent>
            <TabsContent value="ai" className="mt-0">
              <AiTab />
            </TabsContent>
            <TabsContent value="journal" className="mt-0">
              <JournalTab />
            </TabsContent>
            <TabsContent value="learn" className="mt-0">
              <LearnTab />
            </TabsContent>
            <TabsContent value="market" className="mt-0">
              <MarketTab />
            </TabsContent>
            <TabsContent value="goals" className="mt-0">
              <GoalsTab />
            </TabsContent>
            <TabsContent value="retirement" className="mt-0">
              <RetirementTab />
            </TabsContent>
            <TabsContent value="basket" className="mt-0">
              <BasketTab />
            </TabsContent>
            <TabsContent value="issues" className="mt-0">
              <IssuesTab />
            </TabsContent>
            <TabsContent value="action-plan" className="mt-0">
              <Loadable state={snap} skeleton={tabSkeleton()}>
                {(data) => <ActionPlanTab snapshot={data} />}
              </Loadable>
            </TabsContent>
          </main>
        </Tabs>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        actions={paletteActions}
      />
    </>
  );
}
