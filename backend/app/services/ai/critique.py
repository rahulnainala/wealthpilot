"""Phase 29 — multi-agent critique (risk-skeptic).

A second model pass plays a cautious risk manager and challenges the action
plan, so advice is stress-tested rather than one-sided. Opt-in (a button), so
the extra 3070 pass is acceptable. Degrades to None when the model is offline.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.risk import BaseRiskClient

logger = logging.getLogger("wealthpilot.ai")

_SYSTEM = (
    "You are a cautious risk manager reviewing a portfolio action plan. In 2-3 "
    "short bullet points, give the STRONGEST objections or risks to acting on it "
    "now — what could go wrong, what's being overlooked, what's premature. Be "
    "specific and skeptical. No preamble, no follow-ups."
)


async def critique_plan(db: AsyncSession, risk_client: BaseRiskClient) -> str | None:
    """A skeptic's counterpoints to the current daily plan; None if model offline."""
    from app.services.ai.action_agent import build_daily_plan
    from app.services.ai.providers import build_ai_provider, strip_reasoning

    items = await build_daily_plan(db, risk_client)
    if not items:
        return "Nothing pressing to push back on — no actions queued right now."

    plan_text = "\n".join(f"- {it['title']}" for it in items)
    provider = await build_ai_provider()
    if provider is None:
        return None
    try:
        text = await provider.complete(_SYSTEM, f"Action plan:\n{plan_text}")
        return strip_reasoning(text).strip() or None
    except Exception:  # noqa: BLE001 — model busy/offline is a soft skip
        logger.info("critique skipped (provider error)")
        return None
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()
