"""Chat exchange log (AI Phase 6): raw material for LoRA fine-tuning.

Every Q&A through Ask WealthPilot is recorded; once enough good pairs
accumulate (~1k), /api/ai/training-data exports them as JSONL for
fine-tuning the local model on this portfolio's vocabulary.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ChatExchange(Base, TimestampMixin):
    __tablename__ = "chat_exchanges"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(32))  # ollama | anthropic
    tools_used: Mapped[str] = mapped_column(String(512), default="")
