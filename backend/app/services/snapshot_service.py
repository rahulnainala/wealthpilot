"""Build and persist portfolio snapshots from live/mock Kite data.

Orchestrates the impure work — fetch from Kite, load overrides, classify, sum,
persist — around the pure classifier in :mod:`app.analytics.buckets`. On a daily
token expiry it records a FAILED snapshot and marks the session stale so the
frontend can prompt a reconnect.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analytics.buckets import classify_mutual_fund, classify_stock
from app.domain.enums import Bucket, HoldingType, SnapshotStatus
from app.models.bucket_override import InstrumentBucketOverride
from app.models.snapshot import Snapshot, SnapshotHolding
from app.services.kite import BaseKiteService, KiteTokenExpired
from app.services.kite_sessions import get_active_session, mark_session_stale


async def load_bucket_overrides(db: AsyncSession) -> dict[str, Bucket]:
    """Return {SYMBOL -> Bucket} from the override table."""
    result = await db.execute(select(InstrumentBucketOverride))
    return {
        row.symbol.strip().upper(): Bucket(row.bucket)
        for row in result.scalars().all()
    }


async def build_snapshot(db: AsyncSession, kite: BaseKiteService) -> Snapshot:
    """Fetch data, classify, compute totals, and persist an OK snapshot.

    Raises :class:`KiteTokenExpired` if the token has expired (callers decide
    whether to record a failed snapshot).
    """
    holdings = await kite.get_holdings()
    mf_holdings = await kite.get_mf_holdings()
    margins = await kite.get_margins()
    overrides = await load_bucket_overrides(db)

    cash = round(margins.available_cash, 2)
    total_value = cash
    invested = 0.0
    rows: list[SnapshotHolding] = []

    for h in holdings:
        bucket = classify_stock(h.tradingsymbol, overrides)
        rows.append(
            SnapshotHolding(
                symbol=h.tradingsymbol,
                name=None,
                type=HoldingType.STOCK.value,
                bucket=bucket.value,
                qty=h.quantity,
                avg_price=h.average_price,
                last_price=h.last_price,
                value=h.value,
                invested=h.invested,
                pnl=h.pnl,
            )
        )
        total_value += h.value
        invested += h.invested

    for m in mf_holdings:
        rows.append(
            SnapshotHolding(
                symbol=m.isin,
                name=m.fund,
                type=HoldingType.MF.value,
                bucket=classify_mutual_fund().value,
                qty=m.quantity,
                avg_price=m.average_price,
                last_price=m.last_price,
                value=m.value,
                invested=m.invested,
                pnl=m.pnl,
            )
        )
        total_value += m.value
        invested += m.invested

    snapshot = Snapshot(
        status=SnapshotStatus.OK.value,
        total_value=round(total_value, 2),
        invested=round(invested, 2),
        cash=cash,
        holdings=rows,
    )
    db.add(snapshot)
    await db.commit()
    # Re-load with holdings eager-loaded so serialization never triggers a
    # lazy load outside the async greenlet, and server defaults (ts) are set.
    loaded = await db.execute(
        select(Snapshot)
        .where(Snapshot.id == snapshot.id)
        .options(selectinload(Snapshot.holdings))
    )
    return loaded.scalar_one()


async def record_failed_snapshot(db: AsyncSession, error: str) -> Snapshot:
    """Persist a FAILED (value-less) snapshot marking a refresh that couldn't run."""
    snapshot = Snapshot(status=SnapshotStatus.FAILED.value, error=error)
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def refresh_snapshot(db: AsyncSession, kite: BaseKiteService) -> Snapshot:
    """Build a snapshot, converting a token expiry into a failed-snapshot record.

    On :class:`KiteTokenExpired` the active session is marked stale and a FAILED
    snapshot is stored, then the error is re-raised so HTTP callers can return a
    reconnect prompt. The scheduler swallows the re-raise.
    """
    try:
        return await build_snapshot(db, kite)
    except KiteTokenExpired as exc:
        session = await get_active_session(db)
        if session is not None:
            await mark_session_stale(db, session)
        await record_failed_snapshot(db, str(exc))
        raise
