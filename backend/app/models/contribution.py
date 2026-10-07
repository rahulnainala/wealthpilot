"""Manual monthly contribution entries, tracked per bucket."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Contribution(Base, TimestampMixin):
    """A rupee amount contributed to a bucket in a given month.

    ``month`` is normalized to the first day of the month; one row per
    (bucket, month).
    """

    __tablename__ = "contribution"
    __table_args__ = (
        UniqueConstraint("bucket", "month", name="uq_contribution_bucket_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bucket: Mapped[str] = mapped_column(String(16), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
