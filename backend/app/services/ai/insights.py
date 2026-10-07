"""Pilot speaks first: short proactive observations, refreshed on learning runs."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_insight import AiInsight
from app.services.ai.brief_service import _compile_context
from app.services.ai.providers import build_ai_provider
from app.services.risk import BaseRiskClient

logger = logging.getLogger("wealthpilot.ai")

_SYSTEM = (
    "You are Pilot, the owner's portfolio copilot. From the data, write the 2 "
    "most useful one-line observations, most actionable first. First person, "
    "specific, cite the numbers. One observation per line, no numbering, no "
    "preamble, max 140 characters each."
)


async def generate_insights(db: AsyncSession, risk_client: BaseRiskClient) -> int:
    """Regenerate current insights (rule-based watch alerts + model observations).

    Returns how many were written. Watch alerts (Phase 7) are rule-based and
    always available even when the 3070 is off; model observations are a
    best-effort add-on. A dismissed watch alert stays suppressed until its
    condition clears (identified by alert_key).
    """
    from app.services.ai.watch import evaluate_watch

    alerts = await evaluate_watch(db, risk_client)

    # Model observations are optional — skip cleanly if the provider is down.
    model_lines: list[str] = []
    context = await _compile_context(db, risk_client)
    if context is not None:
        provider = await build_ai_provider()
        if provider is not None:
            try:
                text = await provider.complete(_SYSTEM, context)
                model_lines = [
                    ln.strip("-• ").strip() for ln in text.splitlines() if ln.strip()
                ][:2]
            except Exception:  # noqa: BLE001 — model busy/unreachable is a soft skip
                logger.info("insight generation skipped (provider error)")
            finally:
                close = getattr(provider, "close", None)
                if close is not None:
                    await close()

    # Keys the owner has dismissed stay hidden until the condition clears.
    dismissed_keys = set(
        (
            await db.execute(
                select(AiInsight.alert_key).where(
                    AiInsight.dismissed.is_(True), AiInsight.alert_key.is_not(None)
                )
            )
        ).scalars()
    )

    # Wholesale refresh of the live (non-dismissed) set.
    await db.execute(delete(AiInsight).where(AiInsight.dismissed.is_(False)))
    written = 0
    for a in alerts:
        if a.key in dismissed_keys:
            continue
        db.add(
            AiInsight(text=a.text[:280], severity=a.severity, source="watch", alert_key=a.key)
        )
        written += 1
    for ln in model_lines:
        db.add(AiInsight(text=ln[:280], severity="info", source="model"))
        written += 1
    await db.commit()
    return written


async def current_insights(db: AsyncSession) -> list[AiInsight]:
    rows = await db.execute(
        select(AiInsight).where(AiInsight.dismissed.is_(False)).order_by(AiInsight.id)
    )
    return list(rows.scalars())
