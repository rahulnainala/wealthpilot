"""Response models for the analytics endpoints."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    severity: str
    title: str
    message: str
    amount: float | None = None
    pct_of_total: float | None = None
    symbols: list[str] = []


class ActionPlanItem(BaseModel):
    priority: int
    severity: str
    code: str
    title: str
    action: str
    amount: float | None = None
    symbols: list[str] = []


class MFAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    isin: str
    name: str
    category: str
    asset_class: str
    expense_ratio: float
    recommendation: str
    rationale: str
    goal_tag: str | None = None
    alternative_name: str | None = None
    alternative_er: float | None = None
    value: float
    pnl: float
    annual_cost: float


class GoalSimulationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    probability_of_success: float
    median_ending_value: float
    p10_value: float
    p90_value: float
    run_ts: datetime | None = None


class GoalAnalysisRead(BaseModel):
    key: str
    name: str
    months_remaining: int | None = None
    pct_elapsed: float | None = None
    assigned_value: float
    assigned_symbols: list[str] = []
    violations: list[IssueRead] = []
    simulation: GoalSimulationRead | None = None


class ProjectionPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: int
    p10: float
    median: float
    p90: float


class RiskContributionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bucket: str
    contribution: float


class PortfolioRiskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    var: float
    cvar: float
    confidence: float
    annual_volatility: float = 0.0
    max_drawdown: float = 0.0
    contributions: list[RiskContributionRead] = []


class CorrelatedPairRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label_a: str
    label_b: str
    correlation: float


class DiversificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    average_correlation: float
    diversification_ratio: float
    effective_holdings: float
    holdings: int
    top_pairs: list[CorrelatedPairRead] = []


class RealizedExitRead(BaseModel):
    """A sale inferred from the snapshot history.

    ``exit_price`` and everything derived from it are estimates — the app sees
    holdings, never fills — so the UI must label them as such.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str | None = None
    qty: float
    avg_price: float
    exit_price: float
    proceeds: float
    realized_pnl: float
    realized_pnl_pct: float
    full_exit: bool
    exited_on: date
    deployed_at: datetime | None = None


class ExitLedgerRead(BaseModel):
    """Sell-off progress: what has gone, what it made, what is still idle."""

    exits: list[RealizedExitRead] = []
    exited_count: int
    remaining_count: int
    realized_pnl: float
    proceeds_total: float
    undeployed_amount: float
    undeployed_count: int


class ContributionRealityGoal(BaseModel):
    key: str
    name: str
    planned_monthly: float
    actual_monthly: float | None = None
    invested_delta: float
    ratio: float | None = None


class ContributionRealityRead(BaseModel):
    """Modelled SIP vs the contributions the snapshots actually show.

    Goal probabilities are driven by ``planned_monthly``; when the real rate is
    a fraction of it, those odds describe a plan that isn't being funded. This
    endpoint exists so the UI can say so instead of quietly reporting 98%.
    """

    window_days: int
    days_observed: int
    months_observed: float
    sufficient_history: bool
    planned_total: float
    actual_total: float | None = None
    goals: list[ContributionRealityGoal] = []
