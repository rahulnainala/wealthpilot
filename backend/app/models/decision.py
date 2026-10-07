"""Decision journal (Phase 35): why the owner acted — episodic memory."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Decision(Base, TimestampMixin):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(64))       # sold | bought | paused SIP | rebalanced …
    symbol: Mapped[str | None] = mapped_column(String(64), default=None)
    note: Mapped[str] = mapped_column(Text)               # the reasoning
