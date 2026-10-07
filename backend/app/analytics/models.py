"""Shared value objects for the analytics engine (pure, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.enums import Bucket, HoldingType


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


# Ranking used to sort issues / action items most-severe first.
SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.INFO: 2,
}


@dataclass(frozen=True)
class HoldingView:
    """A minimal, framework-free view of one holding for analytics input."""

    symbol: str
    bucket: Bucket
    type: HoldingType
    value: float
    invested: float
    pnl: float
    pnl_pct: float
    name: str | None = None


@dataclass(frozen=True)
class Issue:
    """A detected portfolio issue with severity, human message, and ₹ figure."""

    code: str
    severity: Severity
    title: str
    message: str
    amount: float | None = None
    pct_of_total: float | None = None
    symbols: list[str] = field(default_factory=list)


def total_value(holdings: list[HoldingView], cash: float) -> float:
    """Total portfolio value = holdings market value + cash."""
    return round(sum(h.value for h in holdings) + cash, 2)


def bucket_totals(holdings: list[HoldingView]) -> dict[Bucket, float]:
    """Sum holding market values per bucket (all four buckets present)."""
    totals: dict[Bucket, float] = {b: 0.0 for b in Bucket}
    for holding in holdings:
        totals[holding.bucket] = round(totals[holding.bucket] + holding.value, 2)
    return totals
