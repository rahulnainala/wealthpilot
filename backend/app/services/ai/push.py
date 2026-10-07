"""Phase 15 — Web Push delivery for proactive alerts.

Sends action-level watch alerts to subscribed browsers so they reach the owner
with the app closed. VAPID keys come from settings (empty = push disabled).
Dead subscriptions (404/410) are pruned; already-notified alert keys are tracked
in the settings KV so the same crossing isn't pushed every nightly run.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.push_subscription import PushSubscription

if TYPE_CHECKING:
    from py_vapid import Vapid01

logger = logging.getLogger("wealthpilot.ai")

_NOTIFIED_KEY = "ai.pushed_alert_keys"


def push_enabled() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key)


def _vapid() -> Vapid01:
    """A py_vapid instance from the stored base64url raw private key."""
    from py_vapid import Vapid01

    priv = get_settings().vapid_private_key or ""
    try:
        return Vapid01.from_raw(private_raw=priv.encode())
    except Exception:  # noqa: BLE001 — reconstruct from the raw scalar directly
        import base64

        from cryptography.hazmat.primitives.asymmetric import ec

        raw = base64.urlsafe_b64decode(priv + "=" * (-len(priv) % 4))
        v = Vapid01()
        v._private_key = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
        v._public_key = v._private_key.public_key()
        return v


async def send_push(db: AsyncSession, title: str, body: str, url: str = "/") -> int:
    """Push one message to every subscription; prune dead ones. Returns sent count."""
    if not push_enabled():
        return 0
    from pywebpush import WebPushException, webpush

    settings = get_settings()
    subs = (await db.execute(select(PushSubscription))).scalars().all()
    vapid = _vapid()
    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=vapid,
                vapid_claims={"sub": settings.vapid_subject},
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                await db.execute(
                    delete(PushSubscription).where(PushSubscription.id == sub.id)
                )
            else:
                logger.info("push failed (%s)", exc)
    await db.commit()
    return sent


async def notify_new_action_alerts(db: AsyncSession) -> int:
    """Push any action-severity insight whose key hasn't been notified yet."""
    if not push_enabled():
        return 0
    from app.models.ai_insight import AiInsight
    from app.models.settings import Setting

    rows = (
        (
            await db.execute(
                select(AiInsight).where(
                    AiInsight.dismissed.is_(False),
                    AiInsight.severity == "action",
                    AiInsight.source == "watch",
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0

    setting = (
        await db.execute(select(Setting).where(Setting.key == _NOTIFIED_KEY))
    ).scalar_one_or_none()
    notified = set(setting.value) if setting and isinstance(setting.value, list) else set()

    sent = 0
    for r in rows:
        if r.alert_key in notified:
            continue
        sent += await send_push(db, "WealthPilot alert", r.text, url="/")
        notified.add(r.alert_key)

    if setting is None:
        db.add(Setting(key=_NOTIFIED_KEY, value=sorted(notified)))
    else:
        setting.value = sorted(notified)
    await db.commit()
    return sent
