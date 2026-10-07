"""Snapshot refresh + read endpoints."""

from __future__ import annotations

from datetime import date as date_
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import DbSession, KiteDep
from app.domain.enums import SnapshotStatus
from app.models.snapshot import Snapshot
from app.services.analytics_service import as_utc, ist_date
from app.schemas.snapshot import (
    SnapshotHealthRead,
    SnapshotRead,
    SnapshotSummary,
    to_snapshot_read,
    to_snapshot_summary,
)
from app.services.kite_sessions import get_active_session
from app.services.snapshot_service import refresh_snapshot

#: Beyond this the displayed portfolio is yesterday's news. Snapshots run twice
#: on weekdays, so a full day and a half of silence means the schedule is broken
#: rather than merely between runs.
STALE_AFTER_HOURS = 36.0

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.post("/refresh", response_model=SnapshotRead)
async def refresh(db: DbSession, kite: KiteDep) -> SnapshotRead:
    """Pull live/mock Kite data, compute analytics, and persist a snapshot."""
    snapshot = await refresh_snapshot(db, kite)
    return to_snapshot_read(snapshot)


@router.get("/latest", response_model=SnapshotRead)
async def latest(db: DbSession) -> SnapshotRead:
    """Return the most recent successful snapshot with its holdings."""
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.status == SnapshotStatus.OK.value)
        .options(selectinload(Snapshot.holdings))
        .order_by(Snapshot.ts.desc(), Snapshot.id.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(
            status_code=404, detail="No snapshot yet. Trigger a refresh first."
        )
    return to_snapshot_read(snapshot)


@router.get("/health", response_model=SnapshotHealthRead)
async def health(db: DbSession) -> SnapshotHealthRead:
    """Report how current the portfolio view is, and why it might not be.

    ``failures_since_ok`` counts the scheduled refreshes that have been thrown
    away since the last good one — the signal that the app has gone blind while
    still showing plausible-looking numbers.
    """
    result = await db.execute(
        select(Snapshot).order_by(Snapshot.ts.desc(), Snapshot.id.desc()).limit(200)
    )
    recent = list(result.scalars())

    last_ok = next(
        (s for s in recent if s.status == SnapshotStatus.OK.value), None
    )
    # Failures newer than the last good snapshot; if there has never been a good
    # one, every failure on record counts.
    failures = [
        s
        for s in recent
        if s.status == SnapshotStatus.FAILED.value
        and (last_ok is None or as_utc(s.ts) > as_utc(last_ok.ts))
    ]

    hours_since_ok: float | None = None
    if last_ok is not None:
        hours_since_ok = round(
            (datetime.now(timezone.utc) - as_utc(last_ok.ts)).total_seconds() / 3600, 2
        )

    session = await get_active_session(db)
    return SnapshotHealthRead(
        last_ok_ts=last_ok.ts if last_ok else None,
        hours_since_ok=hours_since_ok,
        is_stale=hours_since_ok is None or hours_since_ok > STALE_AFTER_HOURS,
        failures_since_ok=len(failures),
        last_error=failures[0].error if failures else None,
        session_connected=session is not None,
        session_stale=session is None,
    )


@router.get("/history", response_model=list[SnapshotSummary])
async def history(
    db: DbSession, limit: int = Query(default=90, ge=1, le=365)
) -> list[SnapshotSummary]:
    """Return one snapshot per calendar day (IST) — chronological, oldest first.

    A day can hold several OK refreshes (manual "Refresh" clicks on top of the
    09:45 IST auto-snapshot); collapsing to the latest one per day keeps trend
    charts and any future training export a clean daily series instead of a
    noisy one weighted toward whichever days had the most manual refreshes.
    """
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.status == SnapshotStatus.OK.value)
        .options(selectinload(Snapshot.holdings))
        .order_by(Snapshot.ts.desc(), Snapshot.id.desc())
        .limit(min(limit * 15, 3000))
    )
    by_day: dict[date_, Snapshot] = {}
    for snapshot in result.scalars():
        day = ist_date(snapshot.ts)
        by_day.setdefault(day, snapshot)  # desc order -> first seen is latest
    daily = sorted(by_day.values(), key=lambda s: s.ts)[-limit:]
    return [to_snapshot_summary(s) for s in daily]
