"""Reconstruct realized exits by diffing the snapshot history.

WealthPilot has no trade-history feed — sales are placed in Zerodha and the app
only ever sees the *resulting* holdings. So a sold position doesn't announce
itself; it just stops appearing. This module infers the sale from the gap: a
stock whose quantity drops between two consecutive daily snapshots was sold, at
roughly the last price the app saw while it was still held.

That estimate is the honest limit of what the data supports, and every number
derived from it is presented as an estimate. The alternative — asking the owner
to log each sale by hand — is exactly the bookkeeping the plan already fails at.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as date_

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import HoldingType, SnapshotStatus
from app.models.realized_exit import RealizedExit
from app.models.snapshot import Snapshot
from app.services.analytics_service import as_utc, ist_date

#: Quantity tolerance — share counts are whole or near-whole, so anything below
#: this is float noise rather than a sale.
QTY_EPSILON = 1e-6

#: Suffixes Zerodha attaches to the same underlying instrument. These flip on
#: and off across snapshots (BIRET ↔ BIRET-RR, MINDSPACE ↔ MINDSPACE-RR), and a
#: naive diff reads every flip as a full exit followed by a fresh purchase —
#: which would have manufactured a dozen phantom sales in this portfolio alone.
_ALIAS_SUFFIXES = ("-RR",)


def canonical_symbol(symbol: str) -> str:
    """Collapse broker-side symbol variants onto one stable identity."""
    s = symbol.strip().upper()
    for suffix in _ALIAS_SUFFIXES:
        if s.endswith(suffix) and len(s) > len(suffix):
            return s[: -len(suffix)]
    return s


@dataclass(frozen=True)
class _Position:
    symbol: str
    name: str | None
    qty: float
    avg_price: float
    last_price: float


def _stock_positions(snapshot: Snapshot) -> dict[str, _Position]:
    """Canonical-symbol → position, for the stock side of one snapshot.

    Aliased rows are merged rather than allowed to shadow one another, so a
    snapshot holding both BIRET and BIRET-RR reports their combined quantity.
    """
    merged: dict[str, _Position] = {}
    for h in snapshot.holdings:
        if h.type != HoldingType.STOCK.value:
            continue
        key = canonical_symbol(h.symbol)
        existing = merged.get(key)
        if existing is None:
            merged[key] = _Position(key, h.name, h.qty, h.avg_price, h.last_price)
            continue
        total_qty = existing.qty + h.qty
        merged[key] = _Position(
            key,
            existing.name or h.name,
            total_qty,
            # Quantity-weighted, so the merged cost basis stays meaningful.
            (existing.avg_price * existing.qty + h.avg_price * h.qty) / total_qty
            if total_qty
            else h.avg_price,
            h.last_price,
        )
    return merged


async def _daily_snapshots(db: AsyncSession) -> list[Snapshot]:
    """OK snapshots collapsed to the last one per IST day, oldest first.

    Manual refreshes stack several snapshots onto one day; diffing all of them
    would compare a position against itself repeatedly and, worse, let a single
    mid-day refresh anomaly register as a sale.
    """
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.status == SnapshotStatus.OK.value)
        .options(selectinload(Snapshot.holdings))
        .order_by(Snapshot.ts.desc(), Snapshot.id.desc())
    )
    by_day: dict[date_, Snapshot] = {}
    for snapshot in result.scalars():
        by_day.setdefault(ist_date(snapshot.ts), snapshot)  # desc → first is latest
    return sorted(by_day.values(), key=lambda s: as_utc(s.ts))


async def detect_exits(db: AsyncSession) -> list[RealizedExit]:
    """Scan the snapshot history and persist any newly-found exits.

    Idempotent: re-running over the same history adds nothing, because rows are
    keyed on (symbol, exited_on). Returns only the rows created by this call.
    """
    snapshots = await _daily_snapshots(db)
    if len(snapshots) < 2:
        return []

    existing = {
        (row.symbol, row.exited_on)
        for row in (await db.execute(select(RealizedExit))).scalars()
    }

    created: list[RealizedExit] = []
    previous = _stock_positions(snapshots[0])
    for snapshot in snapshots[1:]:
        current = _stock_positions(snapshot)
        exited_on = ist_date(snapshot.ts)
        for symbol, before in previous.items():
            after_qty = current[symbol].qty if symbol in current else 0.0
            sold_qty = before.qty - after_qty
            if sold_qty <= QTY_EPSILON:
                continue
            if (symbol, exited_on) in existing:
                continue
            proceeds = sold_qty * before.last_price
            cost = sold_qty * before.avg_price
            row = RealizedExit(
                symbol=symbol,
                name=before.name,
                qty=round(sold_qty, 4),
                avg_price=round(before.avg_price, 2),
                exit_price=round(before.last_price, 2),
                proceeds=round(proceeds, 2),
                realized_pnl=round(proceeds - cost, 2),
                full_exit=after_qty <= QTY_EPSILON,
                exited_on=exited_on,
            )
            db.add(row)
            created.append(row)
            existing.add((symbol, exited_on))
        previous = current

    if created:
        await db.commit()
        for row in created:
            await db.refresh(row)
    return created


async def list_exits(db: AsyncSession) -> list[RealizedExit]:
    """All recorded exits, most recent first."""
    result = await db.execute(
        select(RealizedExit).order_by(RealizedExit.exited_on.desc(), RealizedExit.id.desc())
    )
    return list(result.scalars())


async def mark_deployed(
    db: AsyncSession, exit_id: int, deployed: bool = True
) -> RealizedExit | None:
    """Flag an exit's proceeds as routed into the goal funds (or un-flag it)."""
    row = await db.get(RealizedExit, exit_id)
    if row is None:
        return None
    row.deployed_at = datetime.now(UTC) if deployed else None
    await db.commit()
    await db.refresh(row)
    return row
