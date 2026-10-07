"""Tests for the in-process mock risk client."""

from __future__ import annotations

import math

import pytest

from app.services.risk import (
    BucketRisk,
    DiversificationAsset,
    GoalSimInputs,
    RetirementPlanInputs,
    Sleeve,
)
from app.services.risk.mock import MockRiskEngineClient


async def test_health() -> None:
    assert await MockRiskEngineClient().health() is True


async def test_zero_volatility_is_deterministic() -> None:
    client = MockRiskEngineClient()
    out = await client.simulate_goal(
        GoalSimInputs(
            sleeves=[Sleeve("debt", 100000, 0.07, 0.0)],
            monthly_contribution=0.0,
            months_remaining=12,
            target_value=100000.0,
        )
    )
    # Zero vol -> no spread; ending = 100000 * e^0.07 > target -> probability 1.
    assert out.probability_of_success == 1.0
    assert out.p10_value == out.median_ending_value == out.p90_value


async def test_below_target_zero_probability() -> None:
    client = MockRiskEngineClient()
    out = await client.simulate_goal(
        GoalSimInputs([Sleeve("debt", 100000, 0.07, 0.0)], 0.0, 12, 500000.0)
    )
    assert out.probability_of_success == 0.0


async def test_volatility_widens_band() -> None:
    client = MockRiskEngineClient()
    out = await client.simulate_goal(
        GoalSimInputs([Sleeve("equity", 100000, 0.12, 0.20)], 0.0, 120, 300000.0)
    )
    assert out.p90_value > out.median_ending_value > out.p10_value
    assert 0.0 <= out.probability_of_success <= 1.0


async def test_portfolio_risk_contributions_sum_to_var() -> None:
    client = MockRiskEngineClient()
    out = await client.compute_portfolio_risk(
        [
            BucketRisk("growth", 60000, [0.02, -0.05, 0.01, -0.08, 0.03, -0.02]),
            BucketRisk("dividend", 40000, [0.01, -0.02, 0.00, -0.03, 0.01, -0.01]),
        ],
        confidence=0.80,
    )
    assert out.var >= 0.0
    total = sum(c.contribution for c in out.contributions)
    assert abs(total - out.var) < 0.01


async def test_portfolio_risk_empty() -> None:
    out = await MockRiskEngineClient().compute_portfolio_risk([])
    assert out.var == 0.0 and out.cvar == 0.0 and out.contributions == []


async def test_diversification() -> None:
    client = MockRiskEngineClient()
    out = await client.compute_diversification(
        [
            DiversificationAsset("A", 1.0, [0.01, -0.02, 0.03, -0.01, 0.02]),
            DiversificationAsset("B", 1.0, [0.02, -0.04, 0.06, -0.02, 0.04]),  # 2x A
        ]
    )
    assert out.holdings == 2
    assert out.average_correlation > 0.9  # highly correlated
    assert out.effective_holdings == 2.0  # equal weights
    assert len(out.top_pairs) == 1


async def test_portfolio_projection() -> None:
    client = MockRiskEngineClient()
    points = await client.simulate_portfolio_projection(
        [Sleeve("equity", 100000, 0.12, 0.18)], 0.0, 24
    )
    assert len(points) == 24
    assert points[0].month == 1
    assert points[-1].month == 24
    assert points[-1].median > points[0].median  # grows over time
    assert points[-1].p90 >= points[-1].p10
    assert points[-1].p90 - points[-1].p10 > points[0].p90 - points[0].p10


async def test_retirement_plan_zero_vol_is_deterministic() -> None:
    client = MockRiskEngineClient()
    sleeve = Sleeve("debt", 100000.0, 0.12, 0.0)
    out = await client.simulate_retirement_plan(
        RetirementPlanInputs(
            sleeves=[sleeve],
            contribution_schedule=[],
            monthly_contribution=0.0,
            accumulation_months=12,
            target_value=100000.0,
            withdrawal_schedule=[],
            drawdown_months=12,
            num_paths=50,
            seed=1,
        )
    )
    # No contribution, no withdrawal, zero vol -> pure compounding, no spread.
    expected_at_retirement = 100000.0 * math.exp(0.12)
    assert out.median_corpus == pytest.approx(expected_at_retirement, rel=1e-6)
    assert out.p10_corpus == out.median_corpus == out.p90_corpus
    assert out.probability_of_success == 1.0
    assert out.depletion_probability == 0.0
    expected_terminal = 100000.0 * math.exp(0.24)
    assert out.median_terminal_value == pytest.approx(expected_terminal, rel=1e-6)


async def test_retirement_plan_contribution_schedule_steps_up() -> None:
    client = MockRiskEngineClient()
    sleeve = Sleeve("debt", 0.0, 0.0, 0.0)  # no starting balance, no growth
    base = dict(
        sleeves=[sleeve],
        monthly_contribution=1000.0,
        accumulation_months=12,
        target_value=0.0,
        withdrawal_schedule=[],
        drawdown_months=1,
        num_paths=10,
        seed=1,
    )
    flat = await client.simulate_retirement_plan(
        RetirementPlanInputs(contribution_schedule=[], **base)
    )
    stepped = await client.simulate_retirement_plan(
        RetirementPlanInputs(contribution_schedule=[1000.0] * 6 + [2000.0] * 6, **base)
    )
    assert flat.median_corpus == pytest.approx(12_000.0)
    assert stepped.median_corpus == pytest.approx(18_000.0)
    assert stepped.median_corpus > flat.median_corpus


async def test_retirement_plan_tracks_depletion_when_withdrawal_outpaces_growth() -> None:
    client = MockRiskEngineClient()
    sleeve = Sleeve("debt", 10000.0, 0.05, 0.0)
    out = await client.simulate_retirement_plan(
        RetirementPlanInputs(
            sleeves=[sleeve],
            contribution_schedule=[],
            monthly_contribution=0.0,
            accumulation_months=0,
            target_value=0.0,
            withdrawal_schedule=[5000.0] * 6,
            drawdown_months=6,
            num_paths=10,
            seed=1,
        )
    )
    # ₹10k drawing ₹5k/mo at 5%/yr growth runs dry fast — deterministic (zero
    # vol), so every path depletes at the same month.
    assert out.depletion_probability == 1.0
    assert out.median_depletion_month == pytest.approx(3.0)
    assert out.median_terminal_value < 0.01


async def test_retirement_plan_empty_sleeves_is_safe() -> None:
    out = await MockRiskEngineClient().simulate_retirement_plan(
        RetirementPlanInputs(
            sleeves=[],
            contribution_schedule=[],
            monthly_contribution=0.0,
            accumulation_months=12,
            target_value=100000.0,
            withdrawal_schedule=[],
            drawdown_months=12,
            num_paths=10,
            seed=1,
        )
    )
    assert out.bands == []
    assert out.probability_of_success == 0.0
