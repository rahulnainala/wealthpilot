"""Bridge between persisted state and the pure analytics engine.

Loads the latest snapshot + goals + settings out of the database and adapts them
into the framework-free inputs the analytics functions expect.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analytics.goals import GoalView
from app.analytics.models import HoldingView
from app.domain.enums import Bucket, HoldingType, SnapshotStatus
from app.models.goal import Goal
from app.models.settings import Setting
from app.models.snapshot import Snapshot

IST = ZoneInfo("Asia/Kolkata")
EXPENSE_RATIOS_KEY = "expense_ratios"


def today_ist() -> date:
    return datetime.now(IST).date()


def as_utc(ts: datetime) -> datetime:
    """Make a stored timestamp tz-aware (UTC), whatever the driver returned.

    Postgres ``TIMESTAMP WITH TIME ZONE`` hands back aware datetimes, but SQLite
    (tests, local scratch DBs) drops the tzinfo and returns a naive value —
    and a session can hold *both* at once, since an object just added still
    carries the aware datetime it was constructed with while a re-queried one
    comes back naive. Comparing or sorting across that mix raises outright.
    Everything is written as UTC, so naive means UTC here.
    """
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts


def ist_date(ts: datetime) -> date:
    """The IST calendar date of a stored timestamp.

    A naive datetime passed to ``.astimezone()`` is assumed to be in *system
    local time*, which silently yields the wrong date — and on an IST machine
    the error only shows up between UTC-midnight and IST-midnight, so it hides
    for most of the day. Hence the explicit :func:`as_utc` first.
    """
    return as_utc(ts).astimezone(IST).date()


def _pnl_pct(invested: float, pnl: float) -> float:
    return round(pnl / invested * 100, 2) if invested else 0.0


async def latest_holding_views(
    db: AsyncSession,
) -> tuple[list[HoldingView], float] | None:
    """Return (holdings, cash) from the latest OK snapshot, or None if empty."""
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.status == SnapshotStatus.OK.value)
        .options(selectinload(Snapshot.holdings))
        .order_by(Snapshot.ts.desc(), Snapshot.id.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        return None
    views = [
        HoldingView(
            symbol=h.symbol,
            bucket=Bucket(h.bucket),
            type=HoldingType(h.type),
            value=h.value,
            invested=h.invested,
            pnl=h.pnl,
            pnl_pct=_pnl_pct(h.invested, h.pnl),
            name=h.name,
        )
        for h in snapshot.holdings
    ]
    return views, snapshot.cash


async def load_expense_ratio_overrides(db: AsyncSession) -> dict[str, float]:
    """Read editable MF expense-ratio overrides from the settings store."""
    result = await db.execute(select(Setting).where(Setting.key == EXPENSE_RATIOS_KEY))
    setting = result.scalar_one_or_none()
    if setting is None or not isinstance(setting.value, dict):
        return {}
    return {str(k): float(v) for k, v in setting.value.items()}


async def load_goal_views(db: AsyncSession) -> list[Goal]:
    """Load raw Goal rows (ordered)."""
    result = await db.execute(select(Goal).order_by(Goal.id))
    return list(result.scalars().all())


def to_goal_view(goal: Goal) -> GoalView:
    return GoalView(
        key=goal.key,
        name=goal.name,
        start_date=goal.start_date,
        target_date=goal.target_date,
        checkpoint_date=goal.checkpoint_date,
        assigned_isins=list(goal.assigned_isins),
        assigned_buckets=list(goal.assigned_buckets),
    )
