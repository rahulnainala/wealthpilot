"""Compare each goal's modelled SIP against the contributions actually observed.

Every goal probability in this app is a function of ``Goal.monthly_contribution``
— the plan's number. When the money going in is a fraction of that, the
simulation is scoring a plan nobody is funding, and a "98% likely" badge becomes
actively misleading. The only trustworthy record of what was really contributed
is the cost basis in the snapshot history: ``invested`` moves when and only when
units are bought or sold, independent of market value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import SnapshotStatus
from app.models.goal import Goal
from app.models.snapshot import Snapshot
from app.services.analytics_service import ist_date, today_ist

#: How far back to measure. Long enough to smooth a single lumpy month, short
#: enough that a rate change shows up within a quarter.
DEFAULT_WINDOW_DAYS = 90

#: Below this the rate is noise — one purchase over five days annualises into a
#: fantasy, in either direction.
MIN_DAYS_OBSERVED = 14

DAYS_PER_MONTH = 30.44


@dataclass(frozen=True)
class GoalContribution:
    key: str
    name: str
    planned_monthly: float
    actual_monthly: float | None
    invested_delta: float
    ratio: float | None


#: Cost basis drifts by fractions of a rupee as the broker re-rounds averages.
#: Reporting that as a contribution renders "-₹0", which reads as a bug.
NOISE_FLOOR_RUPEES = 1.0


@dataclass(frozen=True)
class ContributionReality:
    window_days: int
    days_observed: int
    months_observed: float
    sufficient_history: bool
    planned_total: float
    actual_total: float | None
    goals: list[GoalContribution]


async def _bounding_snapshots(
    db: AsyncSession, window_days: int
) -> tuple[Snapshot | None, Snapshot | None]:
    """The oldest and newest OK snapshots inside the trailing window."""
    cutoff = today_ist() - timedelta(days=window_days)
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.status == SnapshotStatus.OK.value)
        .options(selectinload(Snapshot.holdings))
        .order_by(Snapshot.ts.asc(), Snapshot.id.asc())
    )
    in_window = [s for s in result.scalars() if ist_date(s.ts) >= cutoff]
    if not in_window:
        return None, None
    return in_window[0], in_window[-1]


def _invested_for(snapshot: Snapshot, symbols: set[str]) -> float:
    return sum(h.invested for h in snapshot.holdings if h.symbol in symbols)


async def contribution_reality(
    db: AsyncSession, window_days: int = DEFAULT_WINDOW_DAYS
) -> ContributionReality:
    goals = list((await db.execute(select(Goal).order_by(Goal.id))).scalars())
    planned_total = round(sum(g.monthly_contribution for g in goals), 2)

    first, last = await _bounding_snapshots(db, window_days)
    days_observed = (
        (ist_date(last.ts) - ist_date(first.ts)).days
        if first is not None and last is not None
        else 0
    )
    sufficient = days_observed >= MIN_DAYS_OBSERVED
    months = round(days_observed / DAYS_PER_MONTH, 2)

    rows: list[GoalContribution] = []
    actual_total = 0.0
    for goal in goals:
        symbols = set(goal.assigned_isins or [])
        delta = 0.0
        if sufficient and first is not None and last is not None and symbols:
            delta = round(
                _invested_for(last, symbols) - _invested_for(first, symbols), 2
            )
            if abs(delta) < NOISE_FLOOR_RUPEES:
                delta = 0.0
        actual = round(delta / months, 2) if sufficient and months > 0 else None
        if actual is not None:
            actual_total += actual
        rows.append(
            GoalContribution(
                key=goal.key,
                name=goal.name,
                planned_monthly=goal.monthly_contribution,
                actual_monthly=actual,
                invested_delta=delta,
                ratio=(
                    round(actual / goal.monthly_contribution, 4)
                    if actual is not None and goal.monthly_contribution > 0
                    else None
                ),
            )
        )

    return ContributionReality(
        window_days=window_days,
        days_observed=days_observed,
        months_observed=months,
        sufficient_history=sufficient,
        planned_total=planned_total,
        actual_total=round(actual_total, 2) if sufficient else None,
        goals=rows,
    )
