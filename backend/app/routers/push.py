"""Web Push endpoints, split out of ai.py (Phase 15). See docs/AI_ROADMAP.md."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import DbSession

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/vapid-key")
async def ai_vapid_key() -> dict[str, str | None]:
    """Public VAPID key for the browser to subscribe with (Phase 15)."""
    from app.config import get_settings

    return {"key": get_settings().vapid_public_key}


class PushSubscribe(BaseModel):
    endpoint: str
    keys: dict[str, str]


@router.post("/subscribe")
async def ai_subscribe(sub: PushSubscribe, db: DbSession) -> dict[str, str]:
    """Register a browser Web Push subscription."""
    from sqlalchemy import select

    from app.models.push_subscription import PushSubscription

    existing = (
        await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == sub.endpoint)
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            PushSubscription(
                endpoint=sub.endpoint,
                p256dh=sub.keys.get("p256dh", ""),
                auth=sub.keys.get("auth", ""),
            )
        )
        await db.commit()
    return {"status": "ok"}


@router.post("/test-push")
async def ai_test_push(db: DbSession) -> dict[str, int]:
    """Send a test push to all subscriptions."""
    from app.services.ai.push import send_push

    n = await send_push(db, "WealthPilot", "Push is working — Pilot will ping you here.")
    return {"sent": n}
