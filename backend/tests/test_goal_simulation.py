"""Tests for the goal-simulation service (input building, hashing, caching)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import HoldingView
from app.domain.enums import Bucket, HoldingType
from app.models.goal import Goal, GoalSimulation
from app.services.goal_simulation import (
    build_goal_sim_inputs,
    input_hash,
    simulate_goal_and_cache,
    solve_required_contribution,
)
from app.services.risk.mock import MockRiskEngineClient

TODAY = date(2026, 7, 7)


def _goal(**kwargs: object) -> Goal:
    defaults: dict[str, object] = {
        "id": 1,
        "key": "x",
        "name": "X",
        "start_date": None,
        "target_date": date(2032, 1, 1),
        "checkpoint_date": None,
        "target_value": 1_000_000.0,
        "monthly_contribution": 5_000.0,
        "assigned_isins": [],
        "assigned_buckets": [],
    }
    defaults.update(kwargs)
    return Goal(**defaults)


def _holdings() -> list[HoldingView]:
    return [
        HoldingView("INFY", Bucket.GROWTH, HoldingType.STOCK, 40000, 35000, 5000, 14.3),
        HoldingView("ITC", Bucket.DIVIDEND, HoldingType.STOCK, 30000, 28000, 2000, 7.1),
        HoldingView("INF179K01YM7", Bucket.MF, HoldingType.MF, 20000, 19000, 1000, 5.3),
    ]


def test_build_inputs_groups_sleeves_by_class() -> None:
    goal = _goal(assigned_buckets=["growth", "dividend"], assigned_isins=["INF179K01YM7"])
    inputs = build_goal_sim_inputs(goal, _holdings(), TODAY, 10_000)
    assert inputs is not None
    classes = {s.bucket for s in inputs.sleeves}
    assert classes == {"equity", "dividend", "debt"}  # INFY, ITC, HDFC STD (debt MF)
    assert inputs.months_remaining == (2032 - 2026) * 12 + (1 - 7)


def test_build_inputs_none_without_target() -> None:
    assert build_goal_sim_inputs(_goal(target_value=None), [], TODAY, 10_000) is None
    assert build_goal_sim_inputs(_goal(target_date=None), [], TODAY, 10_000) is None


def test_input_hash_is_stable_and_sensitive() -> None:
    goal = _goal(assigned_buckets=["growth"])
    a = build_goal_sim_inputs(goal, _holdings(), TODAY, 10_000)
    b = build_goal_sim_inputs(goal, _holdings(), TODAY, 10_000)
    assert a is not None and b is not None
    assert input_hash(a) == input_hash(b)

    goal2 = _goal(assigned_buckets=["growth"], monthly_contribution=9_999.0)
    c = build_goal_sim_inputs(goal2, _holdings(), TODAY, 10_000)
    assert c is not None
    assert input_hash(a) != input_hash(c)


async def test_simulate_and_cache_persists_row(db_session: AsyncSession) -> None:
    goal = Goal(
        key="car",
        name="Car",
        target_date=date(2032, 1, 1),
        target_value=1_000_000.0,
        monthly_contribution=8_000.0,
        assigned_buckets=["growth"],
        assigned_isins=[],
    )
    db_session.add(goal)
    await db_session.commit()
    await db_session.refresh(goal)

    row = await simulate_goal_and_cache(
        db_session, goal, _holdings(), MockRiskEngineClient(), TODAY, 10_000
    )
    assert row is not None
    assert 0.0 <= row.probability_of_success <= 1.0
    assert row.input_hash

    count = (
        await db_session.execute(select(func.count()).select_from(GoalSimulation))
    ).scalar_one()
    assert count == 1


async def test_required_contribution_solver() -> None:
    # A big target far above current holdings needs a positive monthly amount.
    goal = _goal(target_value=5_000_000.0, monthly_contribution=0.0, assigned_buckets=["growth"])
    result = await solve_required_contribution(
        goal, _holdings(), MockRiskEngineClient(), TODAY, 5000, target_probability=0.75
    )
    assert result is not None
    assert result.required_monthly_contribution > 0
    # Probability at the solved contribution meets the target (within search tolerance).
    assert result.probability_of_success >= 0.75 - 0.02


async def test_required_contribution_none_without_target() -> None:
    goal = _goal(target_value=None)
    result = await solve_required_contribution(
        goal, [], MockRiskEngineClient(), TODAY, 5000
    )
    assert result is None
