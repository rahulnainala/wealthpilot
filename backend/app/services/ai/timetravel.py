"""Phase 37 — time-travel: view the portfolio as of any past snapshot date.

Pure read over the snapshots already stored (33+), so this is mostly surfacing
existing history: the latest OK snapshot on or before a chosen date, with its
value, P&L, and top holdings.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import SnapshotStatus
from app.models.snapshot import Snapshot, SnapshotHolding


async def available_dates(db: AsyncSession) -> list[str]:
    rows = (
        await db.execute(
            select(Snapshot.created_at)
            .where(Snapshot.status == SnapshotStatus.OK.value)
            .order_by(Snapshot.id.desc())
            .limit(90)
        )
    ).scalars().all()
    return sorted({r.date().isoformat() for r in rows})


async def snapshot_as_of(db: AsyncSession, date_str: str) -> dict[str, Any] | None:
    try:
        target = datetime.fromisoformat(date_str).replace(tzinfo=UTC) + timedelta(days=1)
    except (ValueError, TypeError):
        return None

    snap = (
        await db.execute(
            select(Snapshot)
            .where(Snapshot.status == SnapshotStatus.OK.value, Snapshot.created_at < target)
            .order_by(Snapshot.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snap is None:
        return None

    top = (
        await db.execute(
            select(SnapshotHolding.symbol, SnapshotHolding.value)
            .where(SnapshotHolding.snapshot_id == snap.id)
            .order_by(SnapshotHolding.value.desc())
            .limit(5)
        )
    ).all()
    return {
        "as_of": snap.created_at.date().isoformat(),
        "total_value": round(snap.total_value, 2),
        "invested": round(snap.invested, 2),
        "pnl": round(snap.total_value - snap.invested, 2),
        "top": [{"symbol": s, "value": round(v, 2)} for s, v in top],
    }
