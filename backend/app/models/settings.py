"""Simple key/value settings store (editable assumptions, expense ratios)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Setting(Base, TimestampMixin):
    """A single JSON-valued setting keyed by name.

    Used for editable assumptions such as approximate MF expense ratios and the
    per-bucket return/volatility assumptions fed to the risk engine.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
