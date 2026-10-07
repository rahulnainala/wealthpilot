"""Phase 24 — model evaluation core (shared by the script and the endpoint).

Scores a model on a fixed question set with cheap, objective heuristics
(grounding, clean FOLLOW-UPS trailer, plausible length) through the real
grounded chat path, and persists each run so the Learn tab can chart quality
across retrains — proof the model improves rather than drifts.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.risk import BaseRiskClient

QUESTIONS = [
    "What is my single biggest risk right now?",
    "Which holding is closest to the +10% sell threshold?",
    "Am I on track for my goals?",
    "How diversified is my portfolio, really?",
    "Explain my VaR in one line.",
    "What should I do this week?",
]
_SCAFFOLD = re.compile(r"q1\s*\|\s*q2|three short question|naturally ask", re.IGNORECASE)


def score_reply(reply: str) -> int:
    grounded = bool(re.search(r"[₹\d]", reply))
    clean = not _SCAFFOLD.search(reply)
    has_followups = "FOLLOW-UPS:" in reply
    length_ok = 40 <= len(reply) <= 1200
    return int(grounded) + int(clean) + int(has_followups) + int(length_ok)


async def run_eval(
    db: AsyncSession, risk_client: BaseRiskClient, model: str
) -> tuple[int, int]:
    """Run the fixed set through `model`; return (score, max_score).

    Restores the live `ollama_model` afterwards — otherwise evaluating a base
    model would silently swap the model the app serves.
    """
    from app.config import get_settings
    from app.services.ai.chat_service import chat

    settings = get_settings()
    original = settings.ollama_model
    settings.ollama_model = model
    try:
        total = 0
        for q in QUESTIONS:
            res = await chat(q, [], db, risk_client)
            reply = (res.reply or "") if res.status == "ok" else ""
            total += score_reply(reply)
        return total, len(QUESTIONS) * 4
    finally:
        settings.ollama_model = original


async def run_and_store_eval(model: str) -> None:
    """Background task: evaluate `model` and persist the result."""
    from app.db import get_sessionmaker
    from app.models.model_eval import ModelEval
    from app.services.risk import build_risk_client

    risk = build_risk_client()
    try:
        async with get_sessionmaker()() as db:
            score, max_score = await run_eval(db, risk, model)
            db.add(ModelEval(model=model, score=score, max_score=max_score))
            await db.commit()
    finally:
        await risk.close()
