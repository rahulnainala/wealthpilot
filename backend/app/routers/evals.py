"""Model-eval endpoints, split out of ai.py (Phase 24/30). See docs/AI_ROADMAP.md."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.dependencies import DbSession

router = APIRouter(prefix="/api/ai", tags=["ai"])


class EvalRead(BaseModel):
    model: str
    score: int
    max_score: int
    at: str


@router.get("/evals", response_model=list[EvalRead])
async def ai_evals(db: DbSession, limit: int = 20) -> list[EvalRead]:
    """Phase 24: recent model-eval scores (newest last for charting)."""
    from sqlalchemy import select

    from app.models.model_eval import ModelEval

    rows = (
        (await db.execute(select(ModelEval).order_by(ModelEval.id.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return [
        EvalRead(
            model=r.model, score=r.score, max_score=r.max_score, at=r.created_at.isoformat()
        )
        for r in reversed(rows)
    ]


@router.post("/run-eval")
async def ai_run_eval(background: BackgroundTasks) -> dict[str, str]:
    """Kick off a model eval in the background (slow: runs the fixed question set)."""
    from app.config import get_settings
    from app.services.ai.eval import run_and_store_eval

    background.add_task(run_and_store_eval, get_settings().ollama_model)
    return {"status": "started"}


@router.post("/ab-eval")
async def ai_ab_eval(
    background: BackgroundTasks, base: str = "qwen2.5:7b"
) -> dict[str, str]:
    """Phase 30: A/B the live model vs a base in the background; recommend keep/revert."""
    from app.config import get_settings
    from app.services.ai.ab_gate import run_ab

    background.add_task(run_ab, get_settings().ollama_model, base)
    return {"status": "started"}


@router.get("/ab-result")
async def ai_ab_result(db: DbSession) -> dict[str, Any]:
    """The latest A/B comparison + swap recommendation."""
    from app.services.ai.ab_gate import get_ab_result

    return await get_ab_result(db)
