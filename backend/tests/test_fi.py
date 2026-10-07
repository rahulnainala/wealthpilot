"""Tests for the inflation-aware FI projection (app.services.ai.fi).

The engine runs in nominal rupees; these cover the two things layered on top —
reading the target as today's purchasing power (inflation floored at 6%) and
modelling the post-sell-off allocation where the legacy dividend basket has
become equity.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai.fi import MIN_INFLATION, fi_projection, retirement_plan_projection
from app.services.kite import build_kite_service
from app.services.risk.mock import MockRiskEngineClient
from app.services.snapshot_service import build_snapshot


@pytest.fixture
def risk() -> MockRiskEngineClient:
    return MockRiskEngineClient()


async def _seeded(db: AsyncSession) -> None:
    """FI reads the latest snapshot, so one has to exist."""
    await build_snapshot(db, build_kite_service())


async def test_target_is_read_as_todays_money_and_inflated(
    db_session: AsyncSession, risk: MockRiskEngineClient
) -> None:
    await _seeded(db_session)

    r = await fi_projection(
        db_session, risk, years=10, target=10_000_000, inflation=0.06, solve_required=False
    )

    assert r is not None
    assert r.target_today == 10_000_000
    # ₹1Cr of today's money needs 1Cr * 1.06^10 ≈ ₹1.79Cr nominal in 10 years.
    assert r.target_nominal == pytest.approx(10_000_000 * 1.06**10, rel=1e-6)
    assert r.target_nominal > r.target_today


async def test_inflation_is_floored_at_the_planning_minimum(
    db_session: AsyncSession, risk: MockRiskEngineClient
) -> None:
    await _seeded(db_session)

    r = await fi_projection(db_session, risk, inflation=0.02, solve_required=False)

    assert r is not None
    assert r.inflation == MIN_INFLATION


async def test_todays_money_columns_are_the_nominal_ones_deflated(
    db_session: AsyncSession, risk: MockRiskEngineClient
) -> None:
    await _seeded(db_session)

    years, inflation = 12, 0.07
    r = await fi_projection(
        db_session, risk, years=years, inflation=inflation, solve_required=False
    )

    assert r is not None
    divisor = (1 + inflation) ** years
    assert r.median_corpus_today == pytest.approx(r.median_corpus / divisor, rel=1e-4)
    assert r.p10_corpus_today == pytest.approx(r.p10_corpus / divisor, rel=1e-4)
    assert r.p90_corpus_today == pytest.approx(r.p90_corpus / divisor, rel=1e-4)
    assert r.sustainable_monthly_income_today == pytest.approx(
        r.sustainable_monthly_income / divisor, rel=1e-4
    )
    # Inflation always erodes, never flatters.
    assert r.median_corpus_today < r.median_corpus


async def test_post_selloff_moves_the_dividend_basket_into_equity(
    db_session: AsyncSession, risk: MockRiskEngineClient
) -> None:
    await _seeded(db_session)

    before = await fi_projection(db_session, risk, post_selloff=False, solve_required=False)
    after = await fi_projection(db_session, risk, post_selloff=True, solve_required=False)

    assert before is not None and after is not None
    # The legacy dividend sleeve is reclassified, so equity share rises...
    assert after.equity_pct > before.equity_pct
    # ...and equity's higher assumed return lifts the median outcome.
    assert after.median_corpus > before.median_corpus


async def test_required_contribution_is_solved_and_beats_an_underfunded_sip(
    db_session: AsyncSession, risk: MockRiskEngineClient
) -> None:
    await _seeded(db_session)

    r = await fi_projection(
        db_session,
        risk,
        years=13,
        target=15_000_000,
        monthly_contribution=15_000,
        solve_required=True,
    )

    assert r is not None
    assert r.target_probability == 0.75
    # This target is badly underfunded at ₹15k/mo, so the solver must ask for more.
    assert r.probability_of_success < 0.75
    assert r.required_monthly_contribution > r.monthly_contribution


async def test_plan_step_up_beats_a_flat_sip(
    db_session: AsyncSession, risk: MockRiskEngineClient
) -> None:
    """The whole reason step-up exists: Travel/Vehicle freeing their SIP into
    FI should out-perform (and out-survive) a flat ₹15k/mo forever."""
    await _seeded(db_session)

    flat = await retirement_plan_projection(
        db_session,
        risk,
        years=13,
        target=15_000_000,
        monthly_contribution=15_000,
        retirement_years=25,
        step_up=False,
    )
    stepped = await retirement_plan_projection(
        db_session,
        risk,
        years=13,
        target=15_000_000,
        monthly_contribution=15_000,
        retirement_years=25,
        step_up=True,
        travel_months=60,  # 5y out — well inside the 13y accumulation window
        vehicle_months=84,  # 7y out
    )

    assert flat is not None and stepped is not None
    assert stepped.probability_of_success >= flat.probability_of_success
    assert stepped.depletion_probability <= flat.depletion_probability
    assert stepped.median_corpus > flat.median_corpus


async def test_plan_bands_span_accumulation_and_drawdown(
    db_session: AsyncSession, risk: MockRiskEngineClient
) -> None:
    await _seeded(db_session)

    r = await retirement_plan_projection(
        db_session, risk, years=3, retirement_years=2, step_up=False
    )

    assert r is not None
    assert r.bands[0].month == 0
    assert r.bands[-1].month == (3 + 2) * 12


async def test_plan_depletion_tracked_when_swr_is_aggressive(
    db_session: AsyncSession, risk: MockRiskEngineClient
) -> None:
    await _seeded(db_session)

    r = await retirement_plan_projection(
        db_session,
        risk,
        years=5,
        target=2_000_000,
        monthly_contribution=5_000,
        swr=0.20,  # far above any sustainable withdrawal rate
        retirement_years=20,
        step_up=False,
    )

    assert r is not None
    assert r.depletion_probability > 0
    assert r.median_depletion_year is not None
    assert r.median_depletion_year >= date.today().year + 5
