"""Tests for planned-vs-actual contribution measurement and snapshot health."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HoldingType, SnapshotStatus
from app.models.goal import Goal
from app.models.snapshot import Snapshot, SnapshotHolding
from app.services.contribution_reality import contribution_reality

FUND = "INF789F01XA0"


def _fund(invested: float, units: float) -> SnapshotHolding:
    return SnapshotHolding(
        symbol=FUND,
        name="UTI Nifty 50",
        type=HoldingType.MF.value,
        bucket="mf",
        qty=units,
        avg_price=invested / units,
        last_price=invested / units,
        value=invested,
        invested=invested,
        pnl=0.0,
    )


async def _history(db: AsyncSession, points: list[tuple[int, float]]) -> None:
    """Persist OK snapshots as (days_ago, invested) pairs."""
    now = datetime.now(UTC)
    for days_ago, invested in points:
        db.add(
            Snapshot(
                ts=now - timedelta(days=days_ago),
                status=SnapshotStatus.OK.value,
                total_value=invested,
                invested=invested,
                cash=0.0,
                holdings=[_fund(invested, 60.0)],
            )
        )
    await db.commit()


async def _goal(db: AsyncSession, monthly: float) -> None:
    db.add(
        Goal(
            key="travel",
            name="Travel Fund",
            monthly_contribution=monthly,
            assigned_isins=[FUND],
            assigned_buckets=[],
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_actual_rate_is_measured_from_cost_basis(
    db_session: AsyncSession,
) -> None:
    """Roughly a month apart, ₹1,000 added → ~₹1,000/mo, not the modelled ₹10k."""
    await _goal(db_session, 10_000.0)
    await _history(db_session, [(30, 9_000.0), (0, 10_000.0)])

    reality = await contribution_reality(db_session)

    assert reality.sufficient_history is True
    goal = reality.goals[0]
    assert goal.invested_delta == pytest.approx(1_000.0)
    assert goal.actual_monthly == pytest.approx(1_014.0, abs=5.0)
    # The gap the UI exists to show: about 10% of the modelled SIP.
    assert goal.ratio is not None and goal.ratio < 0.15


@pytest.mark.asyncio
async def test_short_history_reports_insufficient_rather_than_a_wild_rate(
    db_session: AsyncSession,
) -> None:
    """Two days apart, one purchase must not annualise into a fantasy."""
    await _goal(db_session, 10_000.0)
    await _history(db_session, [(2, 9_000.0), (0, 10_000.0)])

    reality = await contribution_reality(db_session)

    assert reality.sufficient_history is False
    assert reality.actual_total is None
    assert reality.goals[0].actual_monthly is None


@pytest.mark.asyncio
async def test_flat_history_reports_zero_not_none(db_session: AsyncSession) -> None:
    """No contributions is a real, reportable answer — and the current one."""
    await _goal(db_session, 10_000.0)
    await _history(db_session, [(40, 10_000.0), (0, 10_000.0)])

    reality = await contribution_reality(db_session)

    assert reality.sufficient_history is True
    assert reality.goals[0].actual_monthly == 0.0
    assert reality.goals[0].ratio == 0.0


@pytest.mark.asyncio
async def test_health_flags_failures_since_the_last_good_snapshot(
    client, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        Snapshot(
            ts=now - timedelta(days=3),
            status=SnapshotStatus.OK.value,
            total_value=100.0,
            invested=100.0,
            cash=0.0,
        )
    )
    for hours in (40, 20, 4):
        db_session.add(
            Snapshot(
                ts=now - timedelta(hours=hours),
                status=SnapshotStatus.FAILED.value,
                error="No active Zerodha session for scheduled snapshot.",
            )
        )
    await db_session.commit()

    body = (await client.get("/api/snapshots/health")).json()

    assert body["failures_since_ok"] == 3
    assert body["is_stale"] is True
    assert body["hours_since_ok"] > 36
    assert "Zerodha session" in body["last_error"]
