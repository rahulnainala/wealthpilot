"""Shared domain enumerations.

Stored in the database as their string values (portable across Postgres/SQLite,
no native DB enum types to migrate).
"""

from __future__ import annotations

from enum import StrEnum


class Bucket(StrEnum):
    """Portfolio allocation bucket.

    The portfolio is split three ways (growth / dividend / mutual funds) with
    gold and other non-core holdings kept separate in ``OTHER``.
    """

    GROWTH = "growth"
    DIVIDEND = "dividend"
    MF = "mf"
    OTHER = "other"


class HoldingType(StrEnum):
    STOCK = "stock"
    MF = "mf"


class SnapshotStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"


class GoalKey(StrEnum):
    """Stable identifiers for the seeded goals."""

    TRAVEL = "travel"
    VEHICLE = "vehicle"
    EMERGENCY = "emergency"
    FI = "fi"
