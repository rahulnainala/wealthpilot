"""Phase 11 — retrain readiness: track pairs accumulated since the last train.

The baseline (pair count captured when `wealthpilot` was last built) lives in
the `settings` KV table. `pairs_since_train` = current pairs − baseline; once it
crosses RETRAIN_DELTA, the Learn tab suggests a retrain. Growth is organic, so
this nudges without nagging — quality over raw count.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Setting

RETRAIN_DELTA = 150  # new organic pairs that justify a retrain
_BASELINE_KEY = "ai.train.baseline_pairs"


async def get_baseline(db: AsyncSession) -> int:
    row = (
        await db.execute(select(Setting).where(Setting.key == _BASELINE_KEY))
    ).scalar_one_or_none()
    try:
        return int(row.value) if row is not None else 0
    except (TypeError, ValueError):
        return 0


async def set_baseline(db: AsyncSession, pairs: int) -> int:
    row = (
        await db.execute(select(Setting).where(Setting.key == _BASELINE_KEY))
    ).scalar_one_or_none()
    if row is None:
        db.add(Setting(key=_BASELINE_KEY, value=pairs))
    else:
        row.value = pairs
    await db.commit()
    return pairs


def retrain_recommended(pairs: int, baseline: int) -> bool:
    return (pairs - baseline) >= RETRAIN_DELTA
