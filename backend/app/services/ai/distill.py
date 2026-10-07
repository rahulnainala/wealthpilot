"""Phase 3: distill each day's portfolio state into the RAG store.

The nightly learning job writes a dated knowledge note (holdings, risk,
diversification, issues, goal probabilities) into knowledge_chunks. Over
time this is how the AI accumulates memory of THIS portfolio — chat and
briefs can retrieve "what did my risk look like in May" without any file
management. Notes older than the retention window are pruned.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk
from app.services.ai.brief_service import _compile_context
from app.services.analytics_service import load_goal_views, today_ist
from app.services.risk import BaseRiskClient

logger = logging.getLogger("wealthpilot.ai")

_RETENTION_NOTES = 90


async def distill_daily(db: AsyncSession, risk_client: BaseRiskClient) -> bool:
    """Upsert today's portfolio-state note; returns False when no snapshot."""
    context = await _compile_context(db, risk_client)
    if context is None:
        return False

    today = today_ist()
    goals = await load_goal_views(db)
    goal_lines = [
        f"{g.name}: target ₹{g.target_value:,.0f} by {g.target_date}, SIP ₹{g.monthly_contribution:,.0f}/mo"
        for g in goals
        if g.target_value is not None
    ]
    content = (
        f"# Portfolio state {today.isoformat()}\n\n{context}\n\nGoals:\n"
        + "\n".join(goal_lines)
    )

    source = f"portfolio/daily-{today.isoformat()}"
    existing = (
        await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.source == source))
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            KnowledgeChunk(
                source=source,
                title=f"Portfolio State {today.isoformat()}",
                chunk_index=0,
                content=content,
            )
        )
    elif existing.content != content:
        existing.content = content
        existing.embedding = None

    # Prune beyond the retention window (dated sources sort lexicographically).
    dated = (
        (
            await db.execute(
                select(KnowledgeChunk.source)
                .where(KnowledgeChunk.source.like("portfolio/daily-%"))
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    stale = sorted(dated)[:-_RETENTION_NOTES] if len(dated) > _RETENTION_NOTES else []
    if stale:
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source.in_(stale)))

    await db.commit()
    logger.info("distilled portfolio state into %s", source)
    return True
