"""Tests for the snapshot service (build, totals, token-expiry handling)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import Bucket, SnapshotStatus
from app.models.snapshot import Snapshot
from app.schemas.kite import (
    Holding,
    IndexQuote,
    KiteTokenResponse,
    Margins,
    MFHolding,
    MFOrder,
    Position,
)
from app.services.kite import build_kite_service
from app.services.kite.base import BaseKiteService, KiteTokenExpired
from app.services.kite_sessions import get_active_session, store_new_session
from app.services.snapshot_service import build_snapshot, refresh_snapshot


class _ExpiredKite(BaseKiteService):
    """A service whose reads always report an expired token."""

    def get_login_url(self) -> str:
        return "https://kite.zerodha.com/connect/login"

    def exchange_token(self, request_token: str) -> KiteTokenResponse:
        raise KiteTokenExpired("expired")

    async def get_holdings(self) -> list[Holding]:
        raise KiteTokenExpired("token expired at 6 AM IST")

    async def get_mf_holdings(self) -> list[MFHolding]:
        raise KiteTokenExpired("expired")

    async def get_mf_orders(self) -> list[MFOrder]:
        raise KiteTokenExpired("expired")

    async def get_positions(self) -> list[Position]:
        raise KiteTokenExpired("expired")

    async def get_margins(self) -> Margins:
        raise KiteTokenExpired("expired")

    async def get_index_quotes(self) -> list[IndexQuote]:
        raise KiteTokenExpired("expired")


async def test_build_snapshot_totals_and_buckets(db_session: AsyncSession) -> None:
    snapshot = await build_snapshot(db_session, build_kite_service())

    assert snapshot.status == SnapshotStatus.OK.value
    assert len(snapshot.holdings) == 15  # 9 stocks + 6 MFs
    assert snapshot.cash == 320.00

    # total_value == sum of holding values + cash
    holdings_value = round(sum(h.value for h in snapshot.holdings), 2)
    assert snapshot.total_value == round(holdings_value + snapshot.cash, 2)

    # Every MF lands in the MF bucket; gold in OTHER.
    buckets = {h.symbol: h.bucket for h in snapshot.holdings}
    assert buckets["HDFCGOLD"] == Bucket.OTHER.value
    assert buckets["INF789F01XA0"] == Bucket.MF.value


async def test_refresh_records_failed_snapshot_and_marks_session_stale(
    db_session: AsyncSession,
) -> None:
    # An active session exists, then the token expires mid-refresh.
    await store_new_session(
        db_session,
        KiteTokenResponse(access_token="tok", user_id="U1", public_token=None),
    )

    with pytest.raises(KiteTokenExpired):
        await refresh_snapshot(db_session, _ExpiredKite())

    # A FAILED snapshot was recorded...
    failed = (
        await db_session.execute(
            select(func.count())
            .select_from(Snapshot)
            .where(Snapshot.status == SnapshotStatus.FAILED.value)
        )
    ).scalar_one()
    assert failed == 1

    # ...and the session was marked stale so the UI can prompt a reconnect.
    active = await get_active_session(db_session)
    assert active is None
