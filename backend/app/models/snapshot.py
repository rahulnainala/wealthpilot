"""Portfolio snapshot tables (point-in-time value + per-instrument rows)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import SnapshotStatus
from app.models.base import Base, TimestampMixin


class Snapshot(Base, TimestampMixin):
    """A point-in-time valuation of the whole portfolio.

    A ``FAILED`` snapshot (no value rows) records that a scheduled refresh could
    not run — typically because the daily Kite token had expired.
    """

    __tablename__ = "snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default=SnapshotStatus.OK.value, nullable=False
    )
    total_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    invested: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    holdings: Mapped[list[SnapshotHolding]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SnapshotHolding(Base):
    """One instrument's contribution to a snapshot."""

    __tablename__ = "snapshot_holding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("snapshot.id", ondelete="CASCADE"), index=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    type: Mapped[str] = mapped_column(String(8), nullable=False)  # stock | mf
    bucket: Mapped[str] = mapped_column(String(16), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)
    last_price: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    invested: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, nullable=False)

    snapshot: Mapped[Snapshot] = relationship(back_populates="holdings")
