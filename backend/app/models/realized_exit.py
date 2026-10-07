"""Realized exits from the legacy sell-off — the plan's memory of what was sold.

The sell queue is derived from *live* holdings, so a position that has been sold
simply stops appearing and the plan silently forgets it ever existed. That leaves
no exit progress, no realized P&L, and no record that proceeds are waiting to be
redeployed. This table is that memory, reconstructed by diffing snapshots (see
:mod:`app.services.exit_ledger`) rather than typed in by hand, so it stays true
even for sales placed directly in Zerodha.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RealizedExit(Base, TimestampMixin):
    """One reduction (partial or full) of a stock position, inferred from snapshots.

    ``exit_price`` is the last price the app observed while the position was
    still held, not a broker fill price — WealthPilot has no trade-history feed,
    so proceeds and P&L here are estimates and must be labelled as such.
    """

    __tablename__ = "realized_exit"
    __table_args__ = (
        # One exit per symbol per detection day: re-running detection over the
        # same snapshot history must not duplicate rows. The key is a *date*,
        # not a timestamp — a second refresh on the same day moves that day's
        # representative snapshot to a later ts, which under a timestamp key
        # would re-record the identical sale.
        UniqueConstraint("symbol", "exited_on", name="uq_realized_exit_symbol_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    proceeds: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    #: Whether the whole position went, or only part of it.
    full_exit: Mapped[bool] = mapped_column(default=True, nullable=False)
    #: IST date of the first snapshot that no longer showed the shares.
    exited_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    #: Set once the proceeds have been routed into the goal funds.
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
