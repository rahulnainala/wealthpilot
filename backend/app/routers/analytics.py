"""Analytics endpoints: issues, action plan, MF audit, goal analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.goals import analyze_goal
from app.analytics.issues import detect_issues
from app.analytics.mf_audit import audit_mf
from app.analytics.models import HoldingView, Issue
from app.config import get_settings
from app.dependencies import DbSession, RiskDep
from app.domain.enums import HoldingType
from app.domain.exit_plan import (
    EXIT_DEADLINE_LABEL,
    PROCEEDS_SPLIT_LABEL,
    SELL_THRESHOLD_PCT,
)
from app.models.goal import GoalSimulation
from app.models.realized_exit import RealizedExit
from app.schemas.analytics import (
    ActionPlanItem,
    ContributionRealityGoal,
    ContributionRealityRead,
    CorrelatedPairRead,
    DiversificationRead,
    ExitLedgerRead,
    GoalAnalysisRead,
    GoalSimulationRead,
    IssueRead,
    MFAuditRead,
    PortfolioRiskRead,
    ProjectionPointRead,
    RealizedExitRead,
    RiskContributionRead,
)
from app.services.analytics_service import (
    latest_holding_views,
    load_expense_ratio_overrides,
    load_goal_views,
    to_goal_view,
    today_ist,
)
from app.services.contribution_reality import contribution_reality
from app.services.diversification_service import portfolio_diversification
from app.services.exit_ledger import detect_exits, list_exits, mark_deployed
from app.services.market import build_market_data_provider
from app.services.portfolio_projection import portfolio_projection
from app.services.portfolio_risk_service import portfolio_risk

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Recommended action per issue code, used to build the action plan.
#
# These must agree with the investor's written plan, whose two binding rules
# are:
#
#   1. The legacy stock basket exits on a LADDER — sell each name at +10%
#      profit; anything unsold within 3 months of the deadline exits regardless of
#      P&L. Proceeds split 50/30/20 Travel/Vehicle/Emergency. Gold and the ELSS
#      holdings are explicitly out of scope and stay.
#   2. NO NEW MONEY goes into individual stocks. New money is mutual-fund SIPs.
#
# Generic remedies were actively contradicting that plan: the cluster row said
# "trim" (it's a ladder, not a trim) and the drawdown row said "average down"
# — the exact opposite of rule 2. Advice that argues with the strategy is worse
# than no advice, because it only shows up when a position is already down.
_ACTION_BY_CODE: dict[str, str] = {
    "growth_missing_third": (
        "Route new SIP money to the Growth sleeve. New money is mutual funds "
        "only — never individual stocks."
    ),
    "dividend_overweight": (
        f"Resolves itself as the legacy basket exits (+{SELL_THRESHOLD_PCT}% or "
        f"{EXIT_DEADLINE_LABEL}). Nothing to add here — no new money goes to "
        "these names."
    ),
    "psu_energy_cluster": (
        f"Already winding down: sell each name at +{SELL_THRESHOLD_PCT}%, hard "
        f"exit by {EXIT_DEADLINE_LABEL}. Proceeds split {PROCEEDS_SPLIT_LABEL}."
    ),
    "single_symbol_concentration": (
        f"Legacy stocks exit on the +{SELL_THRESHOLD_PCT}%/{EXIT_DEADLINE_LABEL} "
        "ladder. A broad index fund is meant to be large — check this is real "
        "single-company risk before trimming it."
    ),
    "position_too_small": (
        f"It exits on the +{SELL_THRESHOLD_PCT}%/{EXIT_DEADLINE_LABEL} ladder "
        "like the rest of the basket. Don't top it up to fix the size."
    ),
    "position_drawdown": (
        f"Nothing to do. A legacy name being down only means the "
        f"+{SELL_THRESHOLD_PCT}% trigger won't fire — the {EXIT_DEADLINE_LABEL} "
        "backstop exits it either way."
    ),
    "low_cash": (
        "Broker balance, not the emergency fund. Keep enough to cover SIP "
        "debits and charges; this plan doesn't hold dry powder for dips."
    ),
    "gold_overweight": (
        "Hold. Gold is explicitly out of scope for the sell-off — it stays."
    ),
    "duplicate_elss": "Redeem the duplicate ELSS as 3-year locks expire; redirect to Growth.",
}


async def _require_holdings(db: DbSession) -> tuple[list[HoldingView], float]:
    data = await latest_holding_views(db)
    if data is None:
        raise HTTPException(
            status_code=404, detail="No snapshot yet. Trigger a refresh first."
        )
    return data


def _to_action(issue: Issue, priority: int) -> ActionPlanItem:
    return ActionPlanItem(
        priority=priority,
        severity=issue.severity.value,
        code=issue.code,
        title=issue.title,
        action=_ACTION_BY_CODE.get(issue.code, "Review this item."),
        amount=issue.amount,
        symbols=issue.symbols,
    )


@router.get("/issues", response_model=list[IssueRead])
async def issues(db: DbSession) -> list[IssueRead]:
    holdings, cash = await _require_holdings(db)
    return [IssueRead.model_validate(i) for i in detect_issues(holdings, cash)]


@router.get("/action-plan", response_model=list[ActionPlanItem])
async def action_plan(db: DbSession) -> list[ActionPlanItem]:
    holdings, cash = await _require_holdings(db)
    detected = detect_issues(holdings, cash)  # already sorted most-severe first
    return [_to_action(issue, idx + 1) for idx, issue in enumerate(detected)]


@router.get("/mf-audit", response_model=list[MFAuditRead])
async def mf_audit(db: DbSession) -> list[MFAuditRead]:
    holdings, _cash = await _require_holdings(db)
    mf_holdings = [h for h in holdings if h.type == HoldingType.MF]
    overrides = await load_expense_ratio_overrides(db)
    rows = audit_mf(mf_holdings, overrides)
    return [MFAuditRead.model_validate(r) for r in rows]


async def _latest_simulation(
    db: AsyncSession, goal_id: int
) -> GoalSimulation | None:
    result = await db.execute(
        select(GoalSimulation)
        .where(GoalSimulation.goal_id == goal_id)
        .order_by(GoalSimulation.run_ts.desc(), GoalSimulation.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/goals", response_model=list[GoalAnalysisRead])
async def goals_analysis(db: DbSession) -> list[GoalAnalysisRead]:
    holdings, _cash = await _require_holdings(db)
    goals = await load_goal_views(db)
    today = today_ist()

    analyses: list[GoalAnalysisRead] = []
    for goal in goals:
        result = analyze_goal(to_goal_view(goal), holdings, today)
        simulation = await _latest_simulation(db, goal.id)
        analyses.append(
            GoalAnalysisRead(
                key=result.key,
                name=result.name,
                months_remaining=result.months_remaining,
                pct_elapsed=result.pct_elapsed,
                assigned_value=result.assigned_value,
                assigned_symbols=result.assigned_symbols,
                violations=[IssueRead.model_validate(v) for v in result.violations],
                simulation=(
                    GoalSimulationRead.model_validate(simulation)
                    if simulation is not None
                    else None
                ),
            )
        )
    return analyses


@router.get("/engine-health")
async def engine_health(risk: RiskDep) -> dict[str, str]:
    """Liveness of the C++ risk engine (2s deadline — safe to poll)."""
    ok = await risk.health()
    return {"status": "ok" if ok else "down"}


@router.get("/projection", response_model=list[ProjectionPointRead])
async def projection(
    db: DbSession,
    risk: RiskDep,
    years: int = Query(default=10, ge=1, le=40),
) -> list[ProjectionPointRead]:
    """Forward Monte Carlo projection of total portfolio value (C++ engine)."""
    points = await portfolio_projection(
        db, risk, years * 12, get_settings().simulation_paths
    )
    if points is None:
        raise HTTPException(
            status_code=404, detail="No snapshot yet. Trigger a refresh first."
        )
    return [ProjectionPointRead.model_validate(p) for p in points]


@router.get("/portfolio-risk", response_model=PortfolioRiskRead)
async def portfolio_risk_endpoint(
    db: DbSession,
    risk: RiskDep,
    confidence: float = Query(default=0.95, gt=0.5, lt=1.0),
) -> PortfolioRiskRead:
    """Portfolio VaR/CVaR + per-bucket risk contributions (C++ engine)."""
    provider = build_market_data_provider()
    try:
        outcome = await portfolio_risk(db, provider, risk, confidence)
    finally:
        await provider.close()
    if outcome is None:
        raise HTTPException(
            status_code=404, detail="No snapshot yet. Trigger a refresh first."
        )
    return PortfolioRiskRead(
        var=round(outcome.var, 2),
        cvar=round(outcome.cvar, 2),
        confidence=confidence,
        annual_volatility=round(outcome.annual_volatility, 4),
        max_drawdown=round(outcome.max_drawdown, 4),
        contributions=[
            RiskContributionRead(bucket=c.bucket, contribution=round(c.contribution, 2))
            for c in outcome.contributions
        ],
    )


@router.get("/diversification", response_model=DiversificationRead)
async def diversification_endpoint(db: DbSession, risk: RiskDep) -> DiversificationRead:
    """Correlation-based diversification & concentration (C++ engine)."""
    provider = build_market_data_provider()
    try:
        outcome = await portfolio_diversification(db, provider, risk)
    finally:
        await provider.close()
    if outcome is None:
        raise HTTPException(
            status_code=404, detail="Need at least 2 holdings — refresh first."
        )
    return DiversificationRead(
        average_correlation=round(outcome.average_correlation, 3),
        diversification_ratio=round(outcome.diversification_ratio, 3),
        effective_holdings=round(outcome.effective_holdings, 2),
        holdings=outcome.holdings,
        top_pairs=[CorrelatedPairRead.model_validate(p) for p in outcome.top_pairs],
    )


def _to_exit_read(row: RealizedExit) -> RealizedExitRead:
    cost = row.qty * row.avg_price
    return RealizedExitRead(
        id=row.id,
        symbol=row.symbol,
        name=row.name,
        qty=row.qty,
        avg_price=row.avg_price,
        exit_price=row.exit_price,
        proceeds=row.proceeds,
        realized_pnl=row.realized_pnl,
        realized_pnl_pct=round(row.realized_pnl / cost * 100, 2) if cost else 0.0,
        full_exit=row.full_exit,
        exited_on=row.exited_on,
        deployed_at=row.deployed_at,
    )


@router.get("/exits", response_model=ExitLedgerRead)
async def exits(db: DbSession) -> ExitLedgerRead:
    """The realized-exit ledger, refreshed from the snapshot history on read.

    Detection runs here rather than only on snapshot creation so that exits
    which happened while the scheduler was failing — the case this feature
    exists for — are still picked up the moment a good snapshot lands.
    """
    await detect_exits(db)
    rows = await list_exits(db)

    # "Remaining" means legacy stocks still to sell — an unassigned stock, the
    # same definition the Basket and Action Plan use. Goal-assigned stock (the
    # gold hedge) is held by plan, not queued for exit, so counting it would
    # make the sell-off look permanently unfinished.
    holdings, _ = await _require_holdings(db)
    assigned = {
        isin for goal in await load_goal_views(db) for isin in (goal.assigned_isins or [])
    }
    remaining = sum(
        1
        for h in holdings
        if h.type == HoldingType.STOCK and h.symbol not in assigned
    )
    undeployed = [r for r in rows if r.deployed_at is None]

    return ExitLedgerRead(
        exits=[_to_exit_read(r) for r in rows],
        exited_count=sum(1 for r in rows if r.full_exit),
        remaining_count=remaining,
        realized_pnl=round(sum(r.realized_pnl for r in rows), 2),
        proceeds_total=round(sum(r.proceeds for r in rows), 2),
        undeployed_amount=round(sum(r.proceeds for r in undeployed), 2),
        undeployed_count=len(undeployed),
    )


@router.post("/exits/{exit_id}/deploy", response_model=RealizedExitRead)
async def deploy_exit(
    exit_id: int, db: DbSession, deployed: bool = Query(default=True)
) -> RealizedExitRead:
    """Mark an exit's proceeds as routed into the goal funds (or undo that)."""
    row = await mark_deployed(db, exit_id, deployed)
    if row is None:
        raise HTTPException(status_code=404, detail="No such exit.")
    return _to_exit_read(row)


@router.get("/contribution-reality", response_model=ContributionRealityRead)
async def contribution_reality_endpoint(
    db: DbSession, window_days: int = Query(default=90, ge=14, le=730)
) -> ContributionRealityRead:
    """Modelled SIP vs contributions the snapshot history actually shows."""
    reality = await contribution_reality(db, window_days)
    return ContributionRealityRead(
        window_days=reality.window_days,
        days_observed=reality.days_observed,
        months_observed=reality.months_observed,
        sufficient_history=reality.sufficient_history,
        planned_total=reality.planned_total,
        actual_total=reality.actual_total,
        goals=[
            ContributionRealityGoal(
                key=g.key,
                name=g.name,
                planned_monthly=g.planned_monthly,
                actual_monthly=g.actual_monthly,
                invested_delta=g.invested_delta,
                ratio=g.ratio,
            )
            for g in reality.goals
        ],
    )
