"""Persisted Zerodha Kite session (encrypted access token + lifecycle state)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class KiteSession(Base, TimestampMixin):
    """A single Kite Connect login session.

    Kite access tokens expire daily at ~6 AM IST, so at most one session is
    "active" (most recent, not stale). The token is stored Fernet-encrypted;
    ``session_date`` records the IST date it was issued so the scheduler can
    detect an expired token and mark the row stale.
    """

    __tablename__ = "kite_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kite_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    public_token_encrypted: Mapped[str | None] = mapped_column(String, nullable=True)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"KiteSession(id={self.id!r}, user={self.kite_user_id!r}, "
            f"date={self.session_date!r}, stale={self.is_stale!r})"
        )
