import { API_BASE } from "@/lib/config";
import type {
  ActionPlanItem,
  Basket,
  ContributionReality,
  Diversification,
  ExitLedger,
  Fund,
  Goal,
  GoalAnalysis,
  GoalSimulation,
  Issue,
  MarketOverview,
  MFAuditRow,
  MFOrder,
  PortfolioRisk,
  ProjectionPoint,
  RealizedExit,
  RequiredContribution,
  SessionStatus,
  Snapshot,
  SnapshotHealth,
  SnapshotSummary,
  StressTest,
} from "@/lib/types";

export class ApiError extends Error {
  status: number;
  code?: string;
  loginUrl?: string;
  constructor(status: number, message: string, code?: string, loginUrl?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.loginUrl = loginUrl;
  }
}

export function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const t = localStorage.getItem("wp:token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...(init?.headers as Record<string, string> | undefined),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    let code: string | undefined;
    let loginUrl: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail ?? body.message ?? detail;
      code = body.error;
      loginUrl = body.login_url;
    } catch {
      /* non-JSON error body */
    }
    // App-auth expiry/absence → clear token and prompt re-login (AuthGate listens).
    if (res.status === 401 && (code === "auth_required" || detail === "auth_required")) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("wp:token");
        window.dispatchEvent(new Event("wp:auth-required"));
      }
    }
    throw new ApiError(res.status, detail, code, loginUrl);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** App-level auth (Phase 40). */
export const appAuth = {
  config: () => request<{ auth_enabled: boolean }>("/api/auth/config"),
  login: (password: string) =>
    request<{ token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  me: () => request<{ ok: boolean }>("/api/auth/me"),
};

export const api = {
  // Auth
  authStatus: () => request<SessionStatus>("/api/auth/kite/status"),

  // Snapshots
  latestSnapshot: () => request<Snapshot>("/api/snapshots/latest"),
  refreshSnapshot: () =>
    request<Snapshot>("/api/snapshots/refresh", { method: "POST" }),
  snapshotHistory: (limit = 90) =>
    request<SnapshotSummary[]>(`/api/snapshots/history?limit=${limit}`),
  snapshotHealth: () => request<SnapshotHealth>("/api/snapshots/health"),

  // Analytics
  issues: () => request<Issue[]>("/api/analytics/issues"),
  actionPlan: () => request<ActionPlanItem[]>("/api/analytics/action-plan"),
  mfAudit: () => request<MFAuditRow[]>("/api/analytics/mf-audit"),
  goalsAnalysis: () => request<GoalAnalysis[]>("/api/analytics/goals"),
  exitLedger: () => request<ExitLedger>("/api/analytics/exits"),
  markExitDeployed: (id: number, deployed = true) =>
    request<RealizedExit>(
      `/api/analytics/exits/${id}/deploy?deployed=${deployed}`,
      { method: "POST" },
    ),
  contributionReality: () =>
    request<ContributionReality>("/api/analytics/contribution-reality"),
  projection: (years = 10) =>
    request<ProjectionPoint[]>(`/api/analytics/projection?years=${years}`),
  portfolioRisk: () => request<PortfolioRisk>("/api/analytics/portfolio-risk"),
  diversification: () =>
    request<Diversification>("/api/analytics/diversification"),
  engineHealth: () => request<{ status: string }>("/api/analytics/engine-health"),
  aiBrief: (refresh = false) =>
    request<{ status: string; brief: string | null; provider: string | null }>(
      `/api/ai/brief${refresh ? "?refresh=true" : ""}`,
    ),
  aiWeeklyReview: (refresh = false) =>
    request<{ status: string; review: string | null }>(
      `/api/ai/weekly-review${refresh ? "?refresh=true" : ""}`,
    ),
  aiNews: (query: string, k = 5) =>
    request<{ title: string; source: string; published: string; sentiment: number }[]>(
      `/api/ai/news?query=${encodeURIComponent(query)}&k=${k}`,
    ),
  autoExecuteStatus: () => request<{ enabled: boolean }>("/api/execution/auto"),
  setAutoExecute: (enabled: boolean) =>
    request<{ enabled: boolean }>("/api/execution/auto", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  basketPreview: () =>
    request<{
      trims: { symbol: string; asset_class: string; reduce_by: number }[];
      message: string;
    }>("/api/execution/basket-preview"),
  executeGtt: (symbol: string, confirm: boolean) =>
    request<{ status: string; message?: string; gtt_id?: string; order?: unknown }>(
      "/api/execution/gtt",
      { method: "POST", body: JSON.stringify({ symbol, confirm }) },
    ),
  aiOrderDraft: (symbol: string) =>
    request<{
      symbol: string;
      side: string;
      quantity: number;
      trigger_price: number;
      est_proceeds: number;
      threshold_met: boolean;
      gain: number;
      est_ltcg_tax: number;
      routing: { label: string; amount: number }[];
      note: string;
    } | null>(`/api/ai/order-draft?symbol=${encodeURIComponent(symbol)}`),
  aiLearn: () =>
    request<{ distilled: boolean; files: number; chunks_added: number; embedded: number }>(
      "/api/ai/learn",
      { method: "POST" },
    ),
  aiStatus: () =>
    request<{
      model: string;
      ollama_reachable: boolean;
      custom_model_present: boolean;
      loaded: { name: string; vram_gb: number }[];
      chunks_total: number;
      chunks_embedded: number;
      training_pairs: number;
      pairs_since_train: number;
      retrain_recommended: boolean;
      last_memory_date: string | null;
      training_generator_running: boolean;
    }>("/api/ai/status"),
  aiTrainStart: (p?: { target?: number; concurrency?: number; model?: string }) =>
    request<{ running: boolean }>(
      `/api/ai/train/start?target=${p?.target ?? 1000}&concurrency=${p?.concurrency ?? 4}` +
        (p?.model ? `&model=${encodeURIComponent(p.model)}` : ""),
      { method: "POST" },
    ),
  aiTrainStop: () =>
    request<{ running: boolean }>("/api/ai/train/stop", { method: "POST" }),
  aiChat: (message: string, history: { role: string; content: string }[], screen?: string) =>
    request<{ status: string; reply: string | null; tools_used: string[] }>(
      "/api/ai/chat",
      { method: "POST", body: JSON.stringify({ message, history, screen }) },
    ),
  aiChatHistory: (limit = 10) =>
    request<{ role: "user" | "assistant"; content: string }[]>(
      `/api/ai/chat/history?limit=${limit}`,
    ),
  search: (q: string) =>
    request<{ source: string; title: string; content: string }[]>(
      `/api/ai/search?q=${encodeURIComponent(q)}`,
    ),
  trainingData: () =>
    request<
      { messages: { role: string; content: string }[]; meta: { provider: string; tools: string; ts: string } }[]
    >("/api/ai/training-data"),
  saveKnowledge: (title: string, content: string) =>
    request<{ status: string; source: string }>("/api/ai/knowledge", {
      method: "POST",
      body: JSON.stringify({ title, content }),
    }),
  aiInsights: () =>
    request<{ id: number; text: string; severity: string; source: string }[]>(
      "/api/ai/insights",
    ),
  aiDataHealth: () =>
    request<{
      stale: boolean;
      snapshot_age_hours: number | null;
      confidence: string;
      reasons: string[];
    }>("/api/ai/data-health"),
  aiOptimize: () =>
    request<{
      method: string;
      current: { asset_class: string; weight: number; value: number }[];
      target: { asset_class: string; weight: number }[];
      rebalance: { asset_class: string; delta_weight: number; delta_amount: number }[];
      current_vol_est: number;
      target_vol_est: number;
    } | null>("/api/ai/optimize"),
  aiBenchmark: () =>
    request<{
      days: number;
      portfolio_return_pct: number;
      nifty_return_pct: number;
      alpha_pct: number;
      note: string;
    } | null>("/api/ai/benchmark"),
  aiEvals: () =>
    request<{ model: string; score: number; max_score: number; at: string }[]>("/api/ai/evals"),
  aiRunEval: () => request<{ status: string }>("/api/ai/run-eval", { method: "POST" }),
  aiAbEval: () => request<{ status: string }>("/api/ai/ab-eval", { method: "POST" }),
  aiAbResult: () =>
    request<{
      candidate?: string;
      candidate_score?: number;
      base?: string;
      base_score?: number;
      winner?: string;
      recommendation?: string;
      at?: string;
    }>("/api/ai/ab-result"),
  aiCritique: () =>
    request<{ critique: string | null }>("/api/ai/critique", { method: "POST" }),
  aiDailyPlan: () =>
    request<{ date: string | null; items: { severity: string; title: string }[] }>(
      "/api/ai/daily-plan",
    ),
  aiRefreshDailyPlan: () =>
    request<{ items: { severity: string; title: string }[] }>("/api/ai/daily-plan/refresh", {
      method: "POST",
    }),
  aiEarnings: () =>
    request<{ symbol: string; earnings_date: string }[]>("/api/ai/earnings"),
  aiTimeTravelDates: () => request<string[]>("/api/ai/timetravel/dates"),
  aiTimeTravel: (date: string) =>
    request<{
      as_of: string;
      total_value: number;
      invested: number;
      pnl: number;
      top: { symbol: string; value: number }[];
    } | null>(`/api/ai/timetravel?date=${encodeURIComponent(date)}`),
  aiMacro: () =>
    request<{
      indicators: { name: string; symbol: string; price: number; change_pct: number }[];
      energy_exposure_pct: number;
      note: string;
    }>("/api/ai/macro"),
  aiDecisions: () =>
    request<{ id: number; action: string; symbol: string | null; note: string; at: string }[]>(
      "/api/ai/decisions",
    ),
  aiAddDecision: (d: { action: string; symbol?: string | null; note: string }) =>
    request<{ id: number; action: string; symbol: string | null; note: string; at: string }>(
      "/api/ai/decisions",
      { method: "POST", body: JSON.stringify(d) },
    ),
  aiDividends: () =>
    request<{
      assumed_yield_pct: number;
      annual_income: number;
      monthly_avg: number;
      holdings: { symbol: string; annual: number; value: number }[];
      note: string;
    } | null>("/api/ai/dividends"),
  watchlist: () =>
    request<{ id: number; symbol: string; last_price: number | null; change_pct: number | null }[]>(
      "/api/watchlist",
    ),
  addWatch: (symbol: string) =>
    request<{ id: number; symbol: string }>("/api/watchlist", {
      method: "POST",
      body: JSON.stringify({ symbol }),
    }),
  deleteWatch: (id: number) =>
    request<{ status: string }>(`/api/watchlist/${id}`, { method: "DELETE" }),
  screener: () => request<{ ideas: string[] }>("/api/watchlist/screener"),
  netWorth: () =>
    request<{
      portfolio: number;
      external: number;
      net_worth: number;
      by_category: Record<string, number>;
    }>("/api/assets/networth"),
  listAssets: () =>
    request<{ id: number; name: string; category: string; value: number }[]>("/api/assets"),
  addAsset: (a: { name: string; category: string; value: number }) =>
    request<{ id: number; name: string; category: string; value: number }>("/api/assets", {
      method: "POST",
      body: JSON.stringify(a),
    }),
  deleteAsset: (id: number) =>
    request<{ status: string }>(`/api/assets/${id}`, { method: "DELETE" }),
  aiXray: () =>
    request<{
      total: number;
      classes: { asset_class: string; direct: number; fund: number; total: number; weight: number }[];
    } | null>("/api/ai/xray"),
  aiStress: (scenario: string) =>
    request<{
      label: string;
      total_before: number;
      total_after: number;
      change: number;
      change_pct: number;
      top_hits: { symbol: string; shock: number; change: number }[];
    } | null>(`/api/ai/stress?scenario=${encodeURIComponent(scenario)}`),
  aiBacktest: (thresholdPct = 10, window = "2y") =>
    request<{
      window: string;
      threshold_pct: number;
      count?: number;
      triggered_count?: number;
      avg_rule_return_pct?: number;
      avg_buy_hold_return_pct?: number;
      avg_edge_pct?: number;
      rule_wins?: number;
      results: {
        symbol: string;
        name: string;
        triggered: boolean;
        days_to_trigger: number | null;
        rule_return_pct: number;
        buy_hold_return_pct: number;
        edge_pct: number;
      }[];
      note?: string;
      message?: string;
    }>(`/api/ai/backtest?threshold_pct=${thresholdPct}&window=${window}`),
  aiFactors: () =>
    request<{
      factors: {
        factor: string;
        exposure: number;
        tilt: string;
        top_contributors: { name: string; contribution: number }[];
      }[];
      note?: string;
      message?: string;
    }>("/api/ai/factors"),
  aiHedge: () =>
    request<{
      equity_exposure: number;
      protect_pct?: number;
      nifty_spot?: number;
      nifty_put_lots?: number;
      est_premium_cost?: number;
      note?: string;
      message?: string;
    } | null>("/api/ai/hedge"),
  aiFi: (p: {
    years: number;
    target: number;
    monthly: number;
    swr: number;
    inflation: number;
    postSelloff: boolean;
  }) =>
    request<{
      years: number;
      swr: number;
      inflation: number;
      post_selloff: boolean;
      monthly_contribution: number;
      target_today: number;
      target_nominal: number;
      probability_of_success: number;
      median_corpus: number;
      p10_corpus: number;
      p90_corpus: number;
      sustainable_monthly_income: number;
      median_corpus_today: number;
      p10_corpus_today: number;
      p90_corpus_today: number;
      sustainable_monthly_income_today: number;
      required_monthly_contribution: number;
      required_reachable: boolean;
      target_probability: number;
      equity_pct: number;
    } | null>(
      `/api/ai/fi?years=${p.years}&target=${p.target}&monthly=${p.monthly}&swr=${p.swr}` +
        `&inflation=${p.inflation}&post_selloff=${p.postSelloff}`,
    ),
  aiFiPlan: (p: {
    years: number;
    target: number;
    monthly: number;
    swr: number;
    inflation: number;
    postSelloff: boolean;
    retirementYears: number;
    stepUp: boolean;
    travelMonths?: number;
    vehicleMonths?: number;
  }) =>
    request<{
      years: number;
      retirement_years: number;
      swr: number;
      inflation: number;
      post_selloff: boolean;
      step_up: boolean;
      monthly_contribution: number;
      target_today: number;
      target_nominal: number;
      probability_of_success: number;
      median_corpus: number;
      p10_corpus: number;
      p90_corpus: number;
      depletion_probability: number;
      median_depletion_year: number | null;
      median_terminal_value: number;
      median_terminal_value_today: number;
      equity_pct: number;
      bands: {
        month: number;
        p10: number;
        median: number;
        p90: number;
        p10_today: number;
        median_today: number;
        p90_today: number;
      }[];
    } | null>(
      `/api/ai/fi-plan?years=${p.years}&target=${p.target}&monthly=${p.monthly}&swr=${p.swr}` +
        `&inflation=${p.inflation}&post_selloff=${p.postSelloff}&retirement_years=${p.retirementYears}` +
        `&step_up=${p.stepUp}` +
        (p.travelMonths != null ? `&travel_months=${p.travelMonths}` : "") +
        (p.vehicleMonths != null ? `&vehicle_months=${p.vehicleMonths}` : ""),
    ),
  aiChart: (kind: string) =>
    request<{ type: string; title: string; series: { label: string; value: number }[] }>(
      `/api/ai/chart?kind=${encodeURIComponent(kind)}`,
    ),
  aiVapidKey: () => request<{ key: string | null }>("/api/ai/vapid-key"),
  aiSubscribe: (sub: { endpoint: string; keys: { p256dh: string; auth: string } }) =>
    request<{ status: string }>("/api/ai/subscribe", {
      method: "POST",
      body: JSON.stringify(sub),
    }),
  aiDismissInsight: (id: number) =>
    request<{ status: string }>(`/api/ai/insights/${id}/dismiss`, { method: "POST" }),

  // Goals
  goals: () => request<Goal[]>("/api/goals"),
  updateGoal: (id: number, patch: Partial<Goal>) =>
    request<Goal>(`/api/goals/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  simulateGoal: (
    id: number,
    body?: { monthly_contribution?: number; target_value?: number; seed?: number },
  ) =>
    request<GoalSimulation>(`/api/goals/${id}/simulate`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  requiredContribution: (id: number, targetProbability = 0.75) =>
    request<RequiredContribution>(`/api/goals/${id}/required-contribution`, {
      method: "POST",
      body: JSON.stringify({ target_probability: targetProbability }),
    }),
  stressTest: (id: number) =>
    request<StressTest>(`/api/goals/${id}/stress`, { method: "POST" }),
  optimizeGoals: (totalBudget: number, maxSteps = 16) =>
    request<{
      total_budget: number;
      step: number;
      allocations: {
        goal_id: number;
        goal_key: string;
        goal_name: string;
        allocated_monthly: number;
        baseline_probability: number;
        optimized_probability: number;
      }[];
      expected_goals_before: number;
      expected_goals_after: number;
      on_track_after: number;
      goal_count: number;
      unallocated: number;
    }>("/api/goals/optimize", {
      method: "POST",
      body: JSON.stringify({ total_budget: totalBudget, max_steps: maxSteps }),
    }),

  // Basket
  basket: () => request<Basket>("/api/basket"),

  // Funds
  funds: () => request<Fund[]>("/api/funds"),
  fundOrders: (isin: string) => request<MFOrder[]>(`/api/funds/${isin}/orders`),
  fundProjection: (isin: string, years = 10) =>
    request<ProjectionPoint[]>(`/api/funds/${isin}/projection?years=${years}`),

  // Market
  marketOverview: () => request<MarketOverview>("/api/market/overview"),

  // Settings
  getSetting: (key: string) =>
    request<{ key: string; value: unknown }>(`/api/settings/${key}`),
  putSetting: (key: string, value: unknown) =>
    request<{ key: string; value: unknown }>(`/api/settings/${key}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
};
