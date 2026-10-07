"""Phase 16 — statistical anomaly detection over snapshot history.

Fixed thresholds (Phase 7) catch what you thought to check; a z-score over the
recent daily-change distribution catches the *unusual* — a move today that's far
from this portfolio's own normal. Returns a plain message so `watch.py` can wrap
it in an alert (no circular import). Silent until enough history exists.
"""

from __future__ import annotations

import statistics

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import SnapshotStatus
from app.models.snapshot import Snapshot

_LOOKBACK = 30
_MIN_POINTS = 8
_Z_THRESHOLD = 2.5


async def detect_value_anomaly(db: AsyncSession) -> str | None:
    """Message when the latest daily value move is a z-score outlier, else None."""
    rows = (
        (
            await db.execute(
                select(Snapshot.total_value)
                .where(Snapshot.status == SnapshotStatus.OK.value)
                .order_by(Snapshot.id.desc())
                .limit(_LOOKBACK)
            )
        )
        .scalars()
        .all()
    )
    values = list(reversed(rows))  # oldest → newest
    changes = [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1]
    ]
    if len(changes) < _MIN_POINTS:
        return None

    recent = changes[-1]
    history = changes[:-1]
    mean = statistics.fmean(history)
    stdev = statistics.pstdev(history)
    if stdev == 0:
        return None
    z = (recent - mean) / stdev
    if abs(z) < _Z_THRESHOLD:
        return None
    return (
        f"Today's move ({recent * 100:+.1f}%) is a {abs(z):.1f}σ outlier vs this "
        f"portfolio's last {len(changes)} days — unusual, worth a look."
    )
