"""Per-symbol overrides to the default bucket classification."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class InstrumentBucketOverride(Base, TimestampMixin):
    """Force a symbol into a specific bucket, overriding the default map."""

    __tablename__ = "instrument_bucket_override"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    bucket: Mapped[str] = mapped_column(String(16), nullable=False)
