"""Tests for inferring realized exits from the snapshot history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HoldingType, SnapshotStatus
from app.models.snapshot import Snapshot, SnapshotHolding
from app.services.exit_ledger import canonical_symbol, detect_exits, list_exits

BASE = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)


def _stock(symbol: str, qty: float, avg: float, ltp: float) -> SnapshotHolding:
    return SnapshotHolding(
        symbol=symbol,
        name=symbol,
        type=HoldingType.STOCK.value,
        bucket="dividend",
        qty=qty,
        avg_price=avg,
        last_price=ltp,
        value=qty * ltp,
        invested=qty * avg,
        pnl=qty * (ltp - avg),
    )


async def _snapshot(
    db: AsyncSession,
    day_offset: int,
    holdings: list[SnapshotHolding],
    *,
    hour_offset: int = 0,
    status: str = SnapshotStatus.OK.value,
) -> Snapshot:
    snapshot = Snapshot(
        ts=BASE + timedelta(days=day_offset, hours=hour_offset),
        status=status,
        total_value=sum(h.value for h in holdings),
        invested=sum(h.invested for h in holdings),
        cash=0.0,
        holdings=holdings,
    )
    db.add(snapshot)
    await db.commit()
    return snapshot


def test_canonical_symbol_strips_broker_suffix() -> None:
    assert canonical_symbol("biret-rr") == "BIRET"
    assert canonical_symbol("MINDSPACE-RR") == "MINDSPACE"
    assert canonical_symbol("ONGC") == "ONGC"


@pytest.mark.asyncio
async def test_full_exit_is_recorded_with_estimated_proceeds(
    db_session: AsyncSession,
) -> None:
    await _snapshot(db_session, 0, [_stock("BPCL", 4, 290.00, 318.00)])
    await _snapshot(db_session, 1, [])

    created = await detect_exits(db_session)

    assert len(created) == 1
    row = created[0]
    assert row.symbol == "BPCL"
    assert row.qty == 4
    assert row.full_exit is True
    # Proceeds are marked at the last observed price, not a broker fill.
    assert row.proceeds == pytest.approx(1272.00, abs=0.01)
    assert row.realized_pnl == pytest.approx(112.00, abs=0.01)


@pytest.mark.asyncio
async def test_partial_reduction_is_recorded_as_partial(
    db_session: AsyncSession,
) -> None:
    await _snapshot(db_session, 0, [_stock("IOC", 30, 141.10, 150.00)])
    await _snapshot(db_session, 1, [_stock("IOC", 15, 141.10, 150.00)])

    created = await detect_exits(db_session)

    assert len(created) == 1
    assert created[0].qty == 15
    assert created[0].full_exit is False


@pytest.mark.asyncio
async def test_broker_suffix_churn_is_not_an_exit(db_session: AsyncSession) -> None:
    """BIRET ↔ BIRET-RR flips must not read as a sale plus a repurchase."""
    await _snapshot(db_session, 0, [_stock("BIRET-RR", 6, 331.00, 344.00)])
    await _snapshot(db_session, 1, [_stock("BIRET", 6, 331.00, 344.00)])
    await _snapshot(db_session, 2, [_stock("BIRET-RR", 6, 331.00, 344.00)])

    assert await detect_exits(db_session) == []


@pytest.mark.asyncio
async def test_detection_is_idempotent(db_session: AsyncSession) -> None:
    await _snapshot(db_session, 0, [_stock("NMDC", 40, 72.10, 74.00)])
    await _snapshot(db_session, 1, [])

    first = await detect_exits(db_session)
    second = await detect_exits(db_session)

    assert len(first) == 1
    assert second == []
    assert len(await list_exits(db_session)) == 1


@pytest.mark.asyncio
async def test_same_day_refresh_does_not_duplicate_the_exit(
    db_session: AsyncSession,
) -> None:
    """A later refresh on the exit day moves that day's representative snapshot.

    Keyed on a timestamp this re-recorded the identical sale; keyed on the date
    it stays a single row.
    """
    await _snapshot(db_session, 0, [_stock("COALINDIA", 18, 402.10, 431.50)])
    await _snapshot(db_session, 1, [])
    assert len(await detect_exits(db_session)) == 1

    await _snapshot(db_session, 1, [], hour_offset=6)
    assert await detect_exits(db_session) == []
    assert len(await list_exits(db_session)) == 1


@pytest.mark.asyncio
async def test_failed_snapshots_do_not_look_like_a_sell_off(
    db_session: AsyncSession,
) -> None:
    """A failed refresh stores no holdings — it must not empty the portfolio."""
    await _snapshot(db_session, 0, [_stock("ONGC", 26, 262.40, 248.75)])
    await _snapshot(db_session, 1, [], status=SnapshotStatus.FAILED.value)
    await _snapshot(db_session, 2, [_stock("ONGC", 26, 262.40, 248.75)])

    assert await detect_exits(db_session) == []


@pytest.mark.asyncio
async def test_mutual_fund_units_are_out_of_scope(db_session: AsyncSession) -> None:
    """The sell-off is stocks only; MF unit moves are SIPs and redemptions."""
    fund = SnapshotHolding(
        symbol="INF789F01XA0",
        name="UTI Nifty 50",
        type=HoldingType.MF.value,
        bucket="mf",
        qty=62.5,
        avg_price=158.40,
        last_price=168.59,
        value=10536.88,
        invested=9900.0,
        pnl=636.88,
    )
    await _snapshot(db_session, 0, [fund])
    await _snapshot(db_session, 1, [])

    assert await detect_exits(db_session) == []
