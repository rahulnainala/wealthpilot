"""Integration tests for the snapshot endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_kite_service
from app.domain.enums import SnapshotStatus
from app.main import app
from app.models.snapshot import Snapshot
from tests.test_snapshot_service import _ExpiredKite


async def test_refresh_then_latest_and_history(client: AsyncClient) -> None:
    resp = await client.post("/api/snapshots/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert len(body["holdings"]) == 15
    assert body["bucket_values"]  # non-empty

    latest = await client.get("/api/snapshots/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == body["id"]

    history = await client.get("/api/snapshots/history")
    assert history.status_code == 200
    assert len(history.json()) >= 1
    assert "bucket_values" in history.json()[0]


async def test_latest_404_when_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/snapshots/latest")
    assert resp.status_code == 404


async def test_refresh_with_expired_token_returns_reconnect(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    app.dependency_overrides[get_kite_service] = lambda: _ExpiredKite()
    try:
        resp = await client.post("/api/snapshots/refresh")
    finally:
        del app.dependency_overrides[get_kite_service]

    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] == "kite_token_expired"
    assert body["login_url"]

    # A FAILED snapshot was persisted.
    failed = (
        await db_session.execute(
            select(func.count())
            .select_from(Snapshot)
            .where(Snapshot.status == SnapshotStatus.FAILED.value)
        )
    ).scalar_one()
    assert failed == 1


async def test_history_collapses_multiple_refreshes_per_day_to_the_latest(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Three manual refreshes "today" at different total_values, plus one from
    # "yesterday" — history should return exactly one row per day, each the
    # latest for that day. Anchored at 08:00 UTC (13:30 IST) so +/- a few
    # hours can't accidentally cross the IST midnight boundary.
    now = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
    yesterday = now - timedelta(days=1)
    db_session.add_all(
        [
            Snapshot(status=SnapshotStatus.OK.value, total_value=100.0, invested=90.0, cash=10.0, ts=yesterday),
            Snapshot(status=SnapshotStatus.OK.value, total_value=200.0, invested=190.0, cash=10.0, ts=now - timedelta(hours=6)),
            Snapshot(status=SnapshotStatus.OK.value, total_value=210.0, invested=190.0, cash=20.0, ts=now - timedelta(hours=3)),
            Snapshot(status=SnapshotStatus.OK.value, total_value=220.0, invested=190.0, cash=30.0, ts=now),
        ]
    )
    await db_session.commit()

    resp = await client.get("/api/snapshots/history")
    assert resp.status_code == 200
    body = resp.json()

    assert len(body) == 2  # one per calendar day
    assert body[0]["total_value"] == 100.0  # yesterday
    assert body[1]["total_value"] == 220.0  # today's latest, not the earlier 200/210
