"""Tests for the startup snapshot catch-up (app.scheduler.run_startup_catchup).

The stack runs on a laptop that sleeps overnight, so the 09:45 IST cron tick
is frequently missed by more than any reasonable misfire_grace_time. This
catch-up is the backstop: on boot, backfill today's snapshot if it never
landed, instead of silently waiting for tomorrow's tick.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app import scheduler as scheduler_module
from app.domain.enums import SnapshotStatus
from app.models.snapshot import Snapshot

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(autouse=True)
def _bind_scheduler_to_test_engine(
    monkeypatch: pytest.MonkeyPatch, test_engine: AsyncEngine
) -> None:
    """run_startup_catchup opens its own session via app.db.get_sessionmaker;
    point that at the same in-memory engine the db_session fixture uses."""
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(scheduler_module, "get_sessionmaker", lambda: maker)


def _stub_run_daily_snapshot(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    calls: list[bool] = []

    async def _fake() -> None:
        calls.append(True)

    monkeypatch.setattr(scheduler_module, "run_daily_snapshot", _fake)
    return calls


async def test_catchup_runs_when_no_snapshot_exists(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _stub_run_daily_snapshot(monkeypatch)

    await scheduler_module.run_startup_catchup()

    assert calls == [True]


async def test_catchup_skips_when_today_already_has_an_ok_snapshot(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Anchored to "now" in IST rather than a wall-clock literal: between
    # UTC-midnight and IST-midnight the UTC and IST dates differ, and an
    # earlier version of this test only passed outside that window.
    now_ist = datetime.now(IST)
    db_session.add(
        Snapshot(
            status=SnapshotStatus.OK.value,
            total_value=100.0,
            invested=90.0,
            cash=10.0,
            ts=now_ist.astimezone(UTC),
        )
    )
    await db_session.commit()
    calls = _stub_run_daily_snapshot(monkeypatch)

    await scheduler_module.run_startup_catchup()

    assert calls == []


async def test_catchup_skips_for_a_snapshot_that_is_todays_only_in_ist(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A snapshot at 00:30 IST is still 'today' even though it's yesterday in UTC.

    Guards the naive/aware timestamp handling: SQLite drops tzinfo, and a naive
    datetime run through .astimezone() is read as system-local, which silently
    shifts the date across the IST midnight boundary.
    """
    today_ist_midnight = datetime.now(IST).replace(hour=0, minute=30, second=0, microsecond=0)
    db_session.add(
        Snapshot(
            status=SnapshotStatus.OK.value,
            total_value=100.0,
            invested=90.0,
            cash=10.0,
            ts=today_ist_midnight.astimezone(UTC),
        )
    )
    await db_session.commit()
    calls = _stub_run_daily_snapshot(monkeypatch)

    await scheduler_module.run_startup_catchup()

    assert calls == []


async def test_catchup_runs_when_only_a_failed_snapshot_exists_today(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(
        Snapshot(status=SnapshotStatus.FAILED.value, error="token expired", ts=datetime.now(UTC))
    )
    await db_session.commit()
    calls = _stub_run_daily_snapshot(monkeypatch)

    await scheduler_module.run_startup_catchup()

    assert calls == [True]


async def test_catchup_runs_when_latest_ok_snapshot_is_from_a_prior_day(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(
        Snapshot(
            status=SnapshotStatus.OK.value,
            total_value=100.0,
            invested=90.0,
            cash=10.0,
            ts=datetime.now(UTC) - timedelta(days=2),
        )
    )
    await db_session.commit()
    calls = _stub_run_daily_snapshot(monkeypatch)

    await scheduler_module.run_startup_catchup()

    assert calls == [True]
