// Response shapes mirroring the FastAPI backend schemas.

export type Bucket = "growth" | "dividend" | "mf" | "other";
export type Severity = "critical" | "warning" | "info";

export interface SnapshotHolding {
  symbol: string;
  name: string | null;
  type: "stock" | "mf";
  bucket: Bucket;
  qty: number;
  avg_price: number;
  last_price: number;
  value: number;
  invested: number;
  pnl: number;
}

export interface Snapshot {
  id: number;
  ts: string;
  status: "ok" | "failed";
  total_value: number;
  invested: number;
  cash: number;
  error: string | null;
  holdings: SnapshotHolding[];
  bucket_values: Record<string, number>;
}

export interface SnapshotSummary {
  id: number;
  ts: string;
  status: "ok" | "failed";
  total_value: number;
  invested: number;
  cash: number;
  bucket_values: Record<string, number>;
}

export interface Issue {
  code: string;
  severity: Severity;
  title: string;
  message: string;
  amount: number | null;
  pct_of_total: number | null;
  symbols: string[];
}

export interface ActionPlanItem {
  priority: number;
  severity: Severity;
  code: string;
  title: string;
  action: string;
  amount: number | null;
  symbols: string[];
}

export interface MFAuditRow {
  isin: string;
  name: string;
  category: string;
  asset_class: string;
  expense_ratio: number;
  recommendation: "keep" | "keep_grow" | "retire";
  rationale: string;
  goal_tag: string | null;
  alternative_name: string | null;
  alternative_er: number | null;
  value: number;
  pnl: number;
  annual_cost: number;
}

export interface GoalSimulation {
  probability_of_success: number;
  median_ending_value: number;
  p10_value: number;
  p90_value: number;
  run_ts: string | null;
}

export interface RequiredContribution {
  required_monthly_contribution: number;
  probability_of_success: number;
  target_probability: number;
  reachable: boolean;
}

export interface StressScenario {
  label: string;
  shock: number;
  probability_of_success: number;
  median_ending_value: number;
  p10_value: number;
}

export interface StressTest {
  baseline_probability: number;
  scenarios: StressScenario[];
}

export interface ProjectionPoint {
  month: number;
  p10: number;
  median: number;
  p90: number;
}

export interface RiskContribution {
  bucket: string;
  contribution: number;
}

export interface PortfolioRisk {
  var: number;
  cvar: number;
  confidence: number;
  annual_volatility: number;
  max_drawdown: number;
  contributions: RiskContribution[];
}

export interface CorrelatedPair {
  label_a: string;
  label_b: string;
  correlation: number;
}

export interface Diversification {
  average_correlation: number;
  diversification_ratio: number;
  effective_holdings: number;
  holdings: number;
  top_pairs: CorrelatedPair[];
}

export interface GoalAnalysis {
  key: string;
  name: string;
  months_remaining: number | null;
  pct_elapsed: number | null;
  assigned_value: number;
  assigned_symbols: string[];
  violations: Issue[];
  simulation: GoalSimulation | null;
}

export interface Goal {
  id: number;
  key: string;
  name: string;
  start_date: string | null;
  target_date: string | null;
  checkpoint_date: string | null;
  target_value: number | null;
  monthly_contribution: number;
  assigned_isins: string[];
  assigned_buckets: string[];
  notes: string | null;
}

export interface IndexQuote {
  name: string;
  instrument_token: number;
  last_price: number;
  change_pct: number;
}

export interface MarketOverview {
  is_fixture: boolean;
  indices: IndexQuote[];
}

export interface SessionStatus {
  connected: boolean;
  is_stale: boolean;
  user_id: string | null;
  session_date: string | null;
  login_url: string;
}

export interface Contribution {
  id: number;
  bucket: string;
  month: string;
  amount: number;
}

export interface GoalRef {
  key: string;
  name: string;
  target_value: number | null;
}

export interface Fund {
  isin: string;
  name: string;
  category: string;
  asset_class: string;
  recommendation: "keep" | "keep_grow" | "retire";
  goal_tag: string | null;
  units: number;
  avg_nav: number;
  nav: number;
  invested: number;
  value: number;
  pnl: number;
  assigned_goals: GoalRef[];
}

export interface MFOrder {
  order_id: string;
  isin: string;
  fund: string;
  transaction_type: string;
  status: string;
  quantity: number;
  amount: number;
  average_price: number;
  order_timestamp: string | null;
}

export type BasketMode = "core" | "planned" | "hold" | "bonus";

export interface BasketPosition {
  label: string;
  symbol: string | null;
  current_value: number;
  sip_pct: number;
  sip_monthly: number;
  mode: BasketMode;
  note: string;
}

export interface BasketSleeve {
  goal_key: string;
  goal_name: string;
  role: string;
  target_value: number | null;
  current_value: number;
  monthly_contribution: number;
  portfolio_pct: number;
  positions: BasketPosition[];
}

export interface MonthlySplit {
  goal_name: string;
  monthly: number;
  pct: number;
}

export interface LegacyHolding {
  symbol: string;
  name: string;
  current_value: number;
  note: string;
}

export interface Basket {
  total_value: number;
  monthly_total: number;
  monthly_split: MonthlySplit[];
  sleeves: BasketSleeve[];
  legacy: LegacyHolding[];
}

/** A sale inferred from the snapshot history — see backend `exit_ledger`. */
export interface RealizedExit {
  id: number;
  symbol: string;
  name: string | null;
  qty: number;
  avg_price: number;
  /** Last price observed while still held — an estimate, not a broker fill. */
  exit_price: number;
  proceeds: number;
  realized_pnl: number;
  realized_pnl_pct: number;
  full_exit: boolean;
  exited_on: string;
  deployed_at: string | null;
}

export interface ExitLedger {
  exits: RealizedExit[];
  exited_count: number;
  remaining_count: number;
  realized_pnl: number;
  proceeds_total: number;
  undeployed_amount: number;
  undeployed_count: number;
}

export interface SnapshotHealth {
  last_ok_ts: string | null;
  hours_since_ok: number | null;
  is_stale: boolean;
  failures_since_ok: number;
  last_error: string | null;
  session_connected: boolean;
  session_stale: boolean;
}

export interface ContributionRealityGoal {
  key: string;
  name: string;
  planned_monthly: number;
  actual_monthly: number | null;
  invested_delta: number;
  ratio: number | null;
}

export interface ContributionReality {
  window_days: number;
  days_observed: number;
  months_observed: number;
  sufficient_history: boolean;
  planned_total: number;
  actual_total: number | null;
  goals: ContributionRealityGoal[];
}
