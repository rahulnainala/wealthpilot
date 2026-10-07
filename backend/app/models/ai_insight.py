"""Pilot's proactive observations (AI Insights) — regenerated each learning run.

Two sources: `model` (LLM-written observations) and `watch` (Phase 7 rule-based
alerts, e.g. a stock crossing the +10% sell threshold). `severity` drives UI
emphasis; `alert_key` gives watch alerts a stable identity so dismissing one
keeps it suppressed until the underlying condition clears.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AiInsight(Base, TimestampMixin):
    __tablename__ = "ai_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    dismissed: Mapped[bool] = mapped_column(default=False)
    severity: Mapped[str] = mapped_column(String(16), default="info")  # action | watch | info
    source: Mapped[str] = mapped_column(String(16), default="model")   # model | watch
    alert_key: Mapped[str | None] = mapped_column(String(128), default=None)
