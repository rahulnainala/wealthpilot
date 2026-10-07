"""Tests for goal analytics (timeline, assigned value, glide-path rules)."""

from __future__ import annotations

from datetime import date

from app.analytics.goals import GoalView, analyze_goal, analyze_goals
from app.analytics.models import HoldingView
from app.domain.enums import Bucket, GoalKey, HoldingType
from tests._fixtures import mock_holding_views

TODAY = date(2026, 7, 7)


def test_pct_elapsed_and_months_remaining() -> None:
    goal = GoalView(
        key=GoalKey.TRAVEL.value,
        name="Travel Fund",
        start_date=date(2026, 8, 1),
        target_date=date(2030, 2, 1),
        checkpoint_date=None,
        assigned_isins=["INF179K01YM7"],
    )
    result = analyze_goal(goal, mock_holding_views(), TODAY)
    # Today is before the start date -> 0% elapsed.
    assert result.pct_elapsed == 0.0
    assert result.months_remaining == (2030 - 2026) * 12 + (2 - 7)  # 43
    # HDFC Short Term Debt is assigned and held.
    assert result.assigned_value > 0
    assert "INF179K01YM7" in result.assigned_symbols
    # Debt vehicle -> no short-horizon-equity violation.
    assert result.violations == []


def test_travel_flags_equity_in_short_horizon() -> None:
    goal = GoalView(
        key=GoalKey.TRAVEL.value,
        name="Travel Fund",
        start_date=date(2026, 1, 1),
        target_date=date(2029, 1, 1),  # < 4y horizon
        checkpoint_date=None,
        assigned_isins=["INF789F01XA0"],  # UTI Nifty 50 (equity)
    )
    holdings = [
        HoldingView(
            symbol="INF789F01XA0",
            bucket=Bucket.MF,
            type=HoldingType.MF,
            value=50_000,
            invested=45_000,
            pnl=5_000,
            pnl_pct=11.1,
        )
    ]
    result = analyze_goal(goal, holdings, TODAY)
    assert any(v.code == "short_horizon_equity" for v in result.violations)


def test_vehicle_glide_path_after_mid_2029() -> None:
    goal = GoalView(
        key=GoalKey.VEHICLE.value,
        name="Vehicle & Lifestyle Fund",
        start_date=date(2027, 1, 1),
        target_date=date(2031, 5, 1),
        checkpoint_date=date(2026, 12, 1),
        assigned_isins=["INF789F01XA0"],
    )
    holdings = [
        HoldingView(
            symbol="INF789F01XA0",
            bucket=Bucket.MF,
            type=HoldingType.MF,
            value=80_000,
            invested=70_000,
            pnl=10_000,
            pnl_pct=14.3,
        )
    ]
    # Before mid-2029: no glide-path warning.
    assert analyze_goal(goal, holdings, date(2028, 1, 1)).violations == []
    # After mid-2029: glide-path warning fires.
    late = analyze_goal(goal, holdings, date(2029, 9, 1))
    assert any(v.code == "glide_path_due" for v in late.violations)


def test_fi_goal_open_ended() -> None:
    goal = GoalView(
        key=GoalKey.FI.value,
        name="Financial Independence",
        start_date=None,
        target_date=date(2040, 1, 1),
        checkpoint_date=None,
        assigned_buckets=[Bucket.DIVIDEND.value, Bucket.GROWTH.value],
        assigned_isins=["INF879O01027"],
    )
    result = analyze_goal(goal, mock_holding_views(), TODAY)
    assert result.pct_elapsed is None  # open-ended (no start date)
    assert result.assigned_value > 0  # dividend bucket + PPFC
    assert result.violations == []


def test_pct_elapsed_caps_at_100_after_target() -> None:
    goal = GoalView(
        key="misc",
        name="Past goal",
        start_date=date(2020, 1, 1),
        target_date=date(2022, 1, 1),
        checkpoint_date=None,
    )
    assert analyze_goal(goal, [], date(2026, 7, 7)).pct_elapsed == 100.0


def test_short_horizon_with_only_debt_and_gold_has_no_violation() -> None:
    # Travel under 4y but assigned money is non-equity (gold) -> no flag.
    goal = GoalView(
        key=GoalKey.TRAVEL.value,
        name="Travel Fund",
        start_date=date(2026, 1, 1),
        target_date=date(2029, 1, 1),
        checkpoint_date=None,
        assigned_isins=["HDFCGOLD"],
    )
    holdings = [
        HoldingView(
            symbol="HDFCGOLD",
            bucket=Bucket.OTHER,
            type=HoldingType.STOCK,
            value=10_000,
            invested=11_000,
            pnl=-1_000,
            pnl_pct=-9.1,
        )
    ]
    assert analyze_goal(goal, holdings, TODAY).violations == []


def test_analyze_goals_batch() -> None:
    goals = [
        GoalView(
            key=GoalKey.FI.value,
            name="FI",
            start_date=None,
            target_date=date(2040, 1, 1),
            checkpoint_date=None,
            assigned_buckets=[Bucket.GROWTH.value],
        ),
    ]
    results = analyze_goals(goals, mock_holding_views(), TODAY)
    assert len(results) == 1
    assert results[0].key == GoalKey.FI.value
