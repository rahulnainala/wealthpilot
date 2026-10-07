"""Order audit log (Phase 42): every placement attempt, dry-run or real."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OrderAudit(Base, TimestampMixin):
    __tablename__ = "order_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float)
    trigger_price: Mapped[float] = mapped_column(Float)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    # dry_run | placed | failed | blocked
    status: Mapped[str] = mapped_column(String(16), default="pending")
    gtt_id: Mapped[str | None] = mapped_column(String(64), default=None)
    detail: Mapped[str | None] = mapped_column(String(512), default=None)
