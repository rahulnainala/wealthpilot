"""Idempotent seeding of the tracked goals.

Runs on startup: inserts each goal only if its key is absent, so it is safe to
run repeatedly and never clobbers user edits.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import Bucket, GoalKey
from app.models.goal import Goal

# ISINs referenced by goals (see the MF audit in Phase 4).
_HDFC_SHORT_TERM_DEBT = "INF179K01YM7"
_UTI_NIFTY50 = "INF789F01XA0"
_PPFC = "INF879O01027"
_NIPPON_MIDCAP150 = "INF204KB18Z7"
_ZERODHA_ELSS = "INF0R8F01026"


def _default_goals() -> list[Goal]:
    # A fictional investor's goals: the demo and the tests run on these. A real
    # install edits its own rows, and seeding never overwrites them.
    return [
        Goal(
            key=GoalKey.TRAVEL.value,
            name="Travel Fund",
            start_date=date(2026, 8, 1),
            target_date=date(2030, 2, 1),  # ~3.5y horizon
            target_value=600_000.0,
            monthly_contribution=10_000.0,
            assigned_isins=[_UTI_NIFTY50, _PPFC],
            assigned_buckets=[],
            notes=(
                "Horizon under 4 years: flag if any travel-tagged money sits in "
                "pure equity."
            ),
        ),
        Goal(
            key=GoalKey.VEHICLE.value,
            name="Vehicle Fund",
            checkpoint_date=date(2026, 12, 1),
            start_date=date(2027, 1, 1),
            target_date=date(2031, 5, 1),
            target_value=350_000.0,
            monthly_contribution=6_000.0,
            assigned_isins=[_NIPPON_MIDCAP150],
            assigned_buckets=[],
            notes=(
                "Equity is fine until mid-2029, then glide-path to short-duration "
                "debt over 18-24 months."
            ),
        ),
        Goal(
            key=GoalKey.EMERGENCY.value,
            name="Emergency Fund",
            target_date=date(2028, 12, 1),
            target_value=110_000.0,
            monthly_contribution=4_000.0,
            assigned_isins=[_HDFC_SHORT_TERM_DEBT],
            assigned_buckets=[],
            notes="Near-cash. Also takes FI's share while FI is paused.",
        ),
        Goal(
            key=GoalKey.FI.value,
            name="Financial Independence",
            target_date=date(2045, 1, 1),  # open-ended marker
            target_value=20_000_000.0,
            monthly_contribution=0.0,  # paused until Travel completes in 2030
            assigned_isins=[_ZERODHA_ELSS],
            assigned_buckets=[Bucket.DIVIDEND.value, Bucket.GROWTH.value],
            notes="Paused until 2030. ELSS + dividend and growth buckets.",
        ),
    ]


async def seed_goals(db: AsyncSession) -> None:
    """Insert any of the default goals that are not already present."""
    existing = set(
        (await db.execute(select(Goal.key))).scalars().all()
    )
    to_add = [g for g in _default_goals() if g.key not in existing]
    if not to_add:
        return
    db.add_all(to_add)
    await db.commit()
