"""Phase 46 — predictive signals (honest, statistical).

Forecasts near-term *volatility* (EWMA, RiskMetrics-style) and reports recent
*momentum* from the portfolio's own daily-value series. Deliberately NOT a price
oracle — it estimates how choppy things are trending and the recent drift, to
sharpen the watch/sell-timing context. Silent until enough history exists.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snapshot import Snapshot, SnapshotStatus

_LAMBDA = 0.94  # RiskMetrics EWMA decay
_MIN = 8


@dataclass(frozen=True)
class Forecast:
    forecast_vol_annual_pct: float
    momentum_10d_pct: float
    trend: str  # up | down | flat
    days: int


async def forecast_signals(db: AsyncSession) -> Forecast | None:
    values = list(
        reversed(
            (
                await db.execute(
                    select(Snapshot.total_value)
                    .where(Snapshot.status == SnapshotStatus.OK.value)
                    .order_by(Snapshot.id.desc())
                    .limit(60)
                )
            ).scalars().all()
        )
    )
    changes = [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1]
    ]
    if len(changes) < _MIN:
        return None

    var = changes[0] ** 2
    for r in changes[1:]:
        var = _LAMBDA * var + (1 - _LAMBDA) * r * r
    annual_vol = math.sqrt(var) * math.sqrt(252)

    window = changes[-10:] if len(changes) >= 10 else changes
    momentum = math.prod(1 + r for r in window) - 1
    trend = "up" if momentum > 0.01 else "down" if momentum < -0.01 else "flat"
    return Forecast(
        forecast_vol_annual_pct=round(annual_vol * 100, 1),
        momentum_10d_pct=round(momentum * 100, 2),
        trend=trend,
        days=len(changes),
    )
