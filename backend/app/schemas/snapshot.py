"""Response models for snapshots and their trend history."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.snapshot import Snapshot, SnapshotHolding


class SnapshotHoldingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str | None
    type: str
    bucket: str
    qty: float
    avg_price: float
    last_price: float
    value: float
    invested: float
    pnl: float


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    status: str
    total_value: float
    invested: float
    cash: float
    error: str | None = None
    holdings: list[SnapshotHoldingRead] = []
    bucket_values: dict[str, float] = {}


class SnapshotSummary(BaseModel):
    """A snapshot without per-instrument rows — for trend charts."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    status: str
    total_value: float
    invested: float
    cash: float
    bucket_values: dict[str, float] = {}


def bucket_values(holdings: Iterable[SnapshotHolding]) -> dict[str, float]:
    """Sum holding market values per bucket."""
    totals: dict[str, float] = {}
    for holding in holdings:
        totals[holding.bucket] = round(totals.get(holding.bucket, 0.0) + holding.value, 2)
    return totals


def to_snapshot_read(snapshot: Snapshot) -> SnapshotRead:
    read = SnapshotRead.model_validate(snapshot)
    read.bucket_values = bucket_values(snapshot.holdings)
    return read


def to_snapshot_summary(snapshot: Snapshot) -> SnapshotSummary:
    summary = SnapshotSummary.model_validate(snapshot)
    summary.bucket_values = bucket_values(snapshot.holdings)
    return summary


class SnapshotHealthRead(BaseModel):
    """Whether the app's view of the portfolio is current.

    Scheduled refreshes fail whenever the daily Kite token has expired, and
    those failures are silent: the UI keeps rendering the last good snapshot as
    though it were today's. That gap is not cosmetic — it is how a position can
    cross its sell threshold with nothing on screen to say so.
    """

    last_ok_ts: datetime | None = None
    hours_since_ok: float | None = None
    is_stale: bool
    failures_since_ok: int
    last_error: str | None = None
    session_connected: bool
    session_stale: bool
