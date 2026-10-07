"""Goal analytics (pure): timeline progress, assigned value, glide-path rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.analytics.mf_audit import AssetClass, mf_asset_class
from app.analytics.models import HoldingView, Issue, Severity
from app.domain.enums import Bucket, GoalKey, HoldingType

# Vehicle Fund: equity is fine until mid-2029, then glide down.
VEHICLE_GLIDE_START = date(2029, 7, 1)
# Travel Fund: short-horizon money should not sit in equity.
SHORT_HORIZON_YEARS = 4.0


@dataclass(frozen=True)
class GoalView:
    key: str
    name: str
    start_date: date | None
    target_date: date | None
    checkpoint_date: date | None
    assigned_isins: list[str] = field(default_factory=list)
    assigned_buckets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GoalAnalytics:
    key: str
    name: str
    months_remaining: int | None
    pct_elapsed: float | None
    assigned_value: float
    assigned_symbols: list[str]
    violations: list[Issue]


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _pct_elapsed(start: date | None, target: date | None, today: date) -> float | None:
    if start is None or target is None or target <= start:
        return None
    if today <= start:
        return 0.0
    if today >= target:
        return 100.0
    return round((today - start).days / (target - start).days * 100, 2)


def _is_equity(holding: HoldingView) -> bool:
    """Equity = growth/dividend stocks, or an equity-class mutual fund."""
    if holding.bucket in (Bucket.GROWTH, Bucket.DIVIDEND):
        return True
    if holding.type == HoldingType.MF:
        return mf_asset_class(holding.symbol) == AssetClass.EQUITY
    return False


def _assigned(goal: GoalView, holdings: list[HoldingView]) -> list[HoldingView]:
    isins = set(goal.assigned_isins)
    buckets = set(goal.assigned_buckets)
    return [
        h for h in holdings if h.symbol in isins or h.bucket.value in buckets
    ]


def analyze_goal(
    goal: GoalView, holdings: list[HoldingView], today: date
) -> GoalAnalytics:
    assigned = _assigned(goal, holdings)
    assigned_value = round(sum(h.value for h in assigned), 2)
    months_remaining = (
        max(0, _months_between(today, goal.target_date))
        if goal.target_date
        else None
    )
    violations = _violations(goal, assigned, months_remaining, today)

    return GoalAnalytics(
        key=goal.key,
        name=goal.name,
        months_remaining=months_remaining,
        pct_elapsed=_pct_elapsed(goal.start_date, goal.target_date, today),
        assigned_value=assigned_value,
        assigned_symbols=[h.symbol for h in assigned],
        violations=violations,
    )


def _violations(
    goal: GoalView,
    assigned: list[HoldingView],
    months_remaining: int | None,
    today: date,
) -> list[Issue]:
    violations: list[Issue] = []
    equity = [h for h in assigned if _is_equity(h)]
    equity_value = round(sum(h.value for h in equity), 2)

    # Travel Fund: horizon < 4y ⇒ flag equity-held money.
    short_horizon = (
        months_remaining is not None and months_remaining / 12 < SHORT_HORIZON_YEARS
    )
    if goal.key == GoalKey.TRAVEL.value and short_horizon and equity:
        violations.append(
            Issue(
                code="short_horizon_equity",
                severity=Severity.WARNING,
                title="Short-horizon money in equity",
                message=(
                    f"{goal.name} is under {SHORT_HORIZON_YEARS:.0f} years out but "
                    f"₹{equity_value:,.0f} of assigned money is in equity — shift to "
                    "short-duration debt."
                ),
                amount=equity_value,
                symbols=[h.symbol for h in equity],
            )
        )

    # Vehicle Fund: begin glide-path from mid-2029.
    if goal.key == GoalKey.VEHICLE.value and today >= VEHICLE_GLIDE_START and equity:
        violations.append(
            Issue(
                code="glide_path_due",
                severity=Severity.WARNING,
                title="Glide-path shift due",
                message=(
                    f"Past mid-2029: begin shifting ₹{equity_value:,.0f} of {goal.name} "
                    "equity into short-duration debt over the next 18-24 months."
                ),
                amount=equity_value,
                symbols=[h.symbol for h in equity],
            )
        )

    return violations


def analyze_goals(
    goals: list[GoalView], holdings: list[HoldingView], today: date
) -> list[GoalAnalytics]:
    return [analyze_goal(g, holdings, today) for g in goals]
