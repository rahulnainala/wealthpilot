"""Phase 30 — A/B gate for model swaps.

After a retrain, evaluate the candidate model against a base on the fixed
question set and recommend whether to keep it. The app *gates and recommends* —
it can't run the 3070 training or restart itself, so the actual swap
(`OLLAMA_MODEL=…` + restart) stays manual. Result is stored in the settings KV
for the Learn tab.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Setting

_AB_KEY = "ai.ab_result"


async def run_ab(candidate: str, base: str) -> None:
    """Background task: eval candidate vs base, store scores + recommendation."""
    from app.db import get_sessionmaker
    from app.models.model_eval import ModelEval
    from app.services.ai.eval import run_eval
    from app.services.risk import build_risk_client

    risk = build_risk_client()
    try:
        async with get_sessionmaker()() as db:
            c_score, mx = await run_eval(db, risk, candidate)
            b_score, _ = await run_eval(db, risk, base)
            db.add(ModelEval(model=candidate, score=c_score, max_score=mx))
            db.add(ModelEval(model=base, score=b_score, max_score=mx))
            keep = c_score >= b_score
            payload = {
                "candidate": candidate,
                "candidate_score": c_score,
                "base": base,
                "base_score": b_score,
                "max_score": mx,
                "winner": candidate if keep else base,
                "recommendation": (
                    f"Keep {candidate} — it matches or beats {base} ({c_score} vs {b_score})."
                    if keep
                    else f"{base} scores higher ({b_score} vs {c_score}) — consider reverting "
                    f"OLLAMA_MODEL to {base}."
                ),
                "at": datetime.now(timezone.utc).isoformat(),
            }
            row = (
                await db.execute(select(Setting).where(Setting.key == _AB_KEY))
            ).scalar_one_or_none()
            if row is None:
                db.add(Setting(key=_AB_KEY, value=payload))
            else:
                row.value = payload
            await db.commit()
    finally:
        await risk.close()


async def get_ab_result(db: AsyncSession) -> dict:
    row = (await db.execute(select(Setting).where(Setting.key == _AB_KEY))).scalar_one_or_none()
    return row.value if row and isinstance(row.value, dict) else {}
