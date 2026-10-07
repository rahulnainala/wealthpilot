"""Phase 9 — weekly written review.

A longer Sunday-style review by wealthpilot: what changed over the week, goal
progress, where the +10% sell plan stands, and one clear action. Reuses the
brief's computed context, folds in active watch alerts and the week-ago
distilled note for deltas, and caches the result for the week (PgTTLCache) so
it costs one model call. Email would need SMTP (not configured) — this serves
in-app; a Sunday cron pre-warms it.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk
from app.services.ai.brief_service import _compile_context
from app.services.ai.providers import build_ai_provider
from app.services.ai.watch import evaluate_watch
from app.services.analytics_service import today_ist
from app.services.cache import get_shared_cache
from app.services.risk import BaseRiskClient

logger = logging.getLogger("wealthpilot.ai")

_SYSTEM = (
    "You are Pilot, the owner's portfolio copilot, writing the weekly review. "
    "In first person, calm and specific, produce 3 short labelled paragraphs:\n"
    "1) THIS WEEK — what changed vs the week-ago snapshot (values, risk, goals).\n"
    "2) SELL PLAN & GOALS — where legacy holdings sit vs the +10% threshold and "
    "whether goals are on track.\n"
    "3) ONE ACTION — the single most useful thing to do next week.\n"
    "Use ONLY the numbers provided — never invent. Amounts are INR. No preamble, "
    "no disclaimers, no follow-ups."
)


@dataclass(frozen=True)
class WeeklyReview:
    status: str  # "ok" | "unconfigured" | "empty"
    review: str | None = None


async def generate_weekly_review(
    db: AsyncSession, risk_client: BaseRiskClient, refresh: bool = False
) -> WeeklyReview:
    context = await _compile_context(db, risk_client)
    if context is None:
        return WeeklyReview(status="empty")

    # Week-ago distilled note enables real week-over-week deltas.
    wsrc = f"portfolio/daily-{(today_ist() - timedelta(days=7)).isoformat()}"
    wrow = (
        await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.source == wsrc))
    ).scalar_one_or_none()
    if wrow is not None:
        context = f"Week-ago snapshot:\n{wrow.content[:900]}\n\n{context}"

    alerts = await evaluate_watch(db, risk_client)
    if alerts:
        context += "\nActive alerts:\n" + "\n".join(f"- {a.text}" for a in alerts)

    provider = await build_ai_provider()
    if provider is None:
        return WeeklyReview(status="unconfigured")

    async def _factory() -> dict[str, str]:
        text = await provider.complete(_SYSTEM, context)
        return {"review": text.strip()}

    try:
        week = today_ist().isocalendar()
        key = (
            f"ai:weekly:{week.year}-{week.week}:"
            f"{hashlib.sha256(context.encode()).hexdigest()[:12]}"
        )
        if refresh:
            get_shared_cache().invalidate(key)
        cached = await get_shared_cache().get_or_set(key, 7 * 86400.0, _factory)
        return WeeklyReview(status="ok", review=cached["review"])
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()
