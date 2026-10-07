"""Tests for idempotent goal seeding."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import GoalKey
from app.models.goal import Goal
from app.services.seed import seed_goals


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed_goals(db_session)
    await seed_goals(db_session)  # second run must not duplicate

    count = (
        await db_session.execute(select(func.count()).select_from(Goal))
    ).scalar_one()
    assert count == 4

    keys = set((await db_session.execute(select(Goal.key))).scalars().all())
    assert keys == {k.value for k in GoalKey}
