"""Persistence helpers for the Kite session lifecycle.

Encapsulates reading the active session, storing a freshly exchanged token
(encrypted), and marking a session stale when its token expires — keeping this
logic out of the routers.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kite_session import KiteSession
from app.schemas.kite import KiteTokenResponse
from app.security.crypto import encrypt

IST = ZoneInfo("Asia/Kolkata")


def _today_ist() -> date:
    return datetime.now(IST).date()


async def get_active_session(db: AsyncSession) -> KiteSession | None:
    """Return the most recent non-stale session, or None if disconnected."""
    result = await db.execute(
        select(KiteSession)
        .where(KiteSession.is_stale.is_(False))
        .order_by(KiteSession.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def store_new_session(
    db: AsyncSession, token: KiteTokenResponse
) -> KiteSession:
    """Persist a new session (token encrypted), retiring any prior sessions."""
    # A new login supersedes every previous session.
    await db.execute(update(KiteSession).values(is_stale=True))

    session = KiteSession(
        kite_user_id=token.user_id,
        access_token_encrypted=encrypt(token.access_token),
        public_token_encrypted=(
            encrypt(token.public_token) if token.public_token else None
        ),
        session_date=_today_ist(),
        is_stale=False,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def mark_session_stale(db: AsyncSession, session: KiteSession) -> None:
    """Flag a session stale after a ``TokenException`` on a live call."""
    session.is_stale = True
    await db.commit()


async def mark_expired_sessions_stale(db: AsyncSession) -> int:
    """Phase 39: proactively stale any session issued before today (IST).

    Kite tokens die at ~6 AM IST, so a session whose ``session_date`` isn't today
    is dead. Marking it stale up front means the app shows the reconnect banner
    immediately instead of 502/401-ing on the first live call.
    """
    result = cast(
        "CursorResult[Any]",
        await db.execute(
            update(KiteSession)
            .where(KiteSession.is_stale.is_(False), KiteSession.session_date < _today_ist())
            .values(is_stale=True)
        ),
    )
    await db.commit()
    return result.rowcount or 0
