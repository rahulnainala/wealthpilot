"""External assets (Phase 49): net worth beyond the Zerodha book."""

from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ExternalAsset(Base, TimestampMixin):
    __tablename__ = "external_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(32))  # bank|epf|real_estate|gold|insurance|other
    value: Mapped[float] = mapped_column(Float)
