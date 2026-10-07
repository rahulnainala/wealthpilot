"""Portfolio-insight endpoints, split out of ai.py: brief, hedge, forecast,
factors, dividends, xray, stress, fi/fi-plan, tax-summary, optimize,
benchmark, weekly-review, monthly-report. See docs/AI_ROADMAP.md.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.dependencies import DbSession, RiskDep
from app.services.ai.brief_service import generate_brief

router = APIRouter(prefix="/api/ai", tags=["ai"])


class BriefRead(BaseModel):
    status: str  # "ok" | "unconfigured" | "empty"
    brief: str | None = None
    provider: str | None = None


@router.get("/brief", response_model=BriefRead)
async def ai_brief(db: DbSession, risk: RiskDep, refresh: bool = False) -> BriefRead:
    """Plain-language morning brief; cached per portfolio state (opens on alerts)."""
    result = await generate_brief(db, risk, refresh=refresh)
    return BriefRead(status=result.status, brief=result.brief, provider=result.provider)


@router.get("/hedge")
async def ai_hedge(db: DbSession, protect_pct: float = 0.10) -> dict[str, Any] | None:
    """Phase 51: protective-put hedge sizing (heuristic estimate)."""
    from app.services.ai.options import hedge_analysis

    return await hedge_analysis(db, protect_pct)


@router.get("/forecast")
async def ai_forecast(db: DbSession) -> dict[str, Any] | None:
    """Phase 46: EWMA volatility forecast + momentum (not a price prediction)."""
    import dataclasses

    from app.services.ai.forecast import forecast_signals

    f = await forecast_signals(db)
    return None if f is None else dataclasses.asdict(f)


@router.get("/factors")
async def ai_factors(db: DbSession) -> dict[str, Any]:
    """Phase 55: heuristic value/momentum/quality/size factor tilts."""
    from app.services.ai.factors import factor_exposure

    return await factor_exposure(db)


@router.get("/dividends")
async def ai_dividends(db: DbSession) -> dict[str, Any] | None:
    """Phase 34: dividend income forecast (assumed yield, labelled)."""
    from app.services.ai.dividends import dividend_forecast

    return await dividend_forecast(db)


@router.get("/xray")
async def ai_xray(db: DbSession) -> dict[str, Any] | None:
    """Phase 33: asset-class look-through (direct vs via-funds)."""
    from app.services.ai.xray import portfolio_xray

    return await portfolio_xray(db)


@router.get("/stress")
async def ai_stress(db: DbSession, scenario: str = "market") -> dict[str, Any] | None:
    """Phase 32: sector-aware stress scenario (energy|market|rates|gold)."""
    from app.services.ai.stress import run_stress

    return await run_stress(db, scenario)


class FiRead(BaseModel):
    years: int
    swr: float
    inflation: float
    post_selloff: bool
    monthly_contribution: float
    target_today: float
    target_nominal: float
    probability_of_success: float
    median_corpus: float
    p10_corpus: float
    p90_corpus: float
    sustainable_monthly_income: float
    median_corpus_today: float
    p10_corpus_today: float
    p90_corpus_today: float
    sustainable_monthly_income_today: float
    required_monthly_contribution: float
    required_reachable: bool
    target_probability: float
    equity_pct: float


@router.get("/fi", response_model=FiRead | None)
async def ai_fi(
    db: DbSession,
    risk: RiskDep,
    years: int = 15,
    target: float = 30_000_000.0,
    monthly: float = 20_000.0,
    swr: float = 0.035,
    inflation: float = 0.06,
    post_selloff: bool = False,
    solve_required: bool = True,
) -> FiRead | None:
    """Phase 31: FI projection + safe-withdrawal income.

    ``target`` is in today's purchasing power; ``inflation`` (floored at 6%)
    grows it to the nominal corpus actually needed. ``post_selloff`` models the
    dividend basket already sold and reinvested as equity.
    """
    import dataclasses

    from app.services.ai.fi import fi_projection

    r = await fi_projection(
        db, risk, years, target, monthly, swr, inflation, post_selloff, solve_required
    )
    return None if r is None else FiRead(**dataclasses.asdict(r))


class PlanBandRead(BaseModel):
    month: int
    p10: float
    median: float
    p90: float
    p10_today: float
    median_today: float
    p90_today: float


class FiPlanRead(BaseModel):
    years: int
    retirement_years: int
    swr: float
    inflation: float
    post_selloff: bool
    step_up: bool
    monthly_contribution: float
    target_today: float
    target_nominal: float
    probability_of_success: float
    median_corpus: float
    p10_corpus: float
    p90_corpus: float
    depletion_probability: float
    median_depletion_year: int | None
    median_terminal_value: float
    median_terminal_value_today: float
    equity_pct: float
    bands: list[PlanBandRead]


@router.get("/fi-plan", response_model=FiPlanRead | None)
async def ai_fi_plan(
    db: DbSession,
    risk: RiskDep,
    years: int = 15,
    target: float = 30_000_000.0,
    monthly: float = 20_000.0,
    swr: float = 0.035,
    inflation: float = 0.06,
    post_selloff: bool = False,
    retirement_years: int = 25,
    step_up: bool = True,
    travel_months: int | None = None,
    vehicle_months: int | None = None,
) -> FiPlanRead | None:
    """Full glide-path: accumulation + drawdown on one continuous path.

    Unlike ``/fi`` (a snapshot at the retirement date), this carries
    sequence-of-returns risk across the retirement boundary and reports
    whether/when the corpus runs dry during ``retirement_years`` of drawdown.
    ``step_up`` models FI's SIP growing as Travel/Vehicle complete and free
    their SIP share (``travel_months``/``vehicle_months`` — months from today
    until each completes, read off the real goal dates by the caller).
    """
    import dataclasses

    from app.services.ai.fi import retirement_plan_projection

    r = await retirement_plan_projection(
        db,
        risk,
        years,
        target,
        monthly,
        swr,
        inflation,
        post_selloff,
        retirement_years,
        step_up,
        travel_months,
        vehicle_months,
    )
    return None if r is None else FiPlanRead(**dataclasses.asdict(r))


@router.get("/monthly-report")
async def ai_monthly_report(db: DbSession, risk: RiskDep) -> Response:
    """Phase 22: on-demand monthly PDF statement."""
    from datetime import date

    from app.services.ai.report import monthly_report_pdf

    pdf = await monthly_report_pdf(db, risk)
    if pdf is None:
        return Response(status_code=204)
    fname = f"wealthpilot-{date.today():%Y-%m}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


class BenchmarkRead(BaseModel):
    days: int
    portfolio_return_pct: float
    nifty_return_pct: float
    alpha_pct: float
    note: str


@router.get("/benchmark", response_model=BenchmarkRead | None)
async def ai_benchmark(db: DbSession) -> BenchmarkRead | None:
    """Phase 21: portfolio vs NIFTY 50 over the recent window."""
    import dataclasses

    from app.services.ai.benchmark import benchmark_vs_nifty

    b = await benchmark_vs_nifty(db)
    return None if b is None else BenchmarkRead(**dataclasses.asdict(b))


class TaxSummaryRead(BaseModel):
    total_unrealized_gain: float
    est_ltcg_tax: float
    est_stcg_tax: float
    harvest_candidates: list[dict[str, Any]]
    note: str


@router.get("/tax-summary", response_model=TaxSummaryRead | None)
async def ai_tax_summary(db: DbSession) -> TaxSummaryRead | None:
    """Phase 20: portfolio tax read (LTCG/STCG estimate + harvest candidates)."""
    from app.services.ai.tax import tax_summary

    t = await tax_summary(db)
    if t is None:
        return None
    return TaxSummaryRead(
        total_unrealized_gain=t.total_unrealized_gain, est_ltcg_tax=t.est_ltcg_tax,
        est_stcg_tax=t.est_stcg_tax, harvest_candidates=t.harvest_candidates, note=t.note,
    )


class OptimizeRead(BaseModel):
    method: str
    current: list[dict[str, Any]]
    target: list[dict[str, Any]]
    rebalance: list[dict[str, Any]]
    current_vol_est: float
    target_vol_est: float


@router.get("/optimize", response_model=OptimizeRead | None)
async def ai_optimize(db: DbSession) -> OptimizeRead | None:
    """Phase 19: risk-parity target allocation + rebalance suggestion."""
    import dataclasses

    from app.services.ai.optimize import optimize_portfolio

    r = await optimize_portfolio(db)
    return None if r is None else OptimizeRead(**dataclasses.asdict(r))


class WeeklyReviewRead(BaseModel):
    status: str  # "ok" | "unconfigured" | "empty"
    review: str | None = None


@router.get("/weekly-review", response_model=WeeklyReviewRead)
async def ai_weekly_review(
    db: DbSession, risk: RiskDep, refresh: bool = False
) -> WeeklyReviewRead:
    """Phase 9: longer weekly review (what changed, sell plan & goals, one action)."""
    from app.services.ai.weekly_review import generate_weekly_review

    result = await generate_weekly_review(db, risk, refresh=refresh)
    return WeeklyReviewRead(status=result.status, review=result.review)
