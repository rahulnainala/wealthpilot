"""Phase 21 — benchmark the portfolio against NIFTY 50.

Chains the portfolio's daily value changes (from Snapshot history) and NIFTY's
daily returns (Yahoo ^NSEI) over the same number of recent trading days, then
reports each cumulative return and the alpha. The portfolio series includes SIP
inflows, so it's an approximation — labelled as such. Empty when NIFTY data or
enough history is unavailable.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import SnapshotStatus
from app.models.snapshot import Snapshot

logger = logging.getLogger("wealthpilot.ai")

_NIFTY = "^NSEI"
_MIN_DAYS = 3


async def _nifty_daily_returns() -> list[float]:
    """NIFTY 50 daily returns from Yahoo's chart (index symbol has no .NS suffix)."""
    try:
        async with httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            resp = await client.get(
                f"/v8/finance/chart/{_NIFTY}", params={"interval": "1d", "range": "6mo"}
            )
            resp.raise_for_status()
            closes = resp.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.info("NIFTY benchmark fetch skipped (%s)", exc)
        return []
    prices = [c for c in closes if c]
    return [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
        if prices[i - 1]
    ]


@dataclass(frozen=True)
class Benchmark:
    days: int
    portfolio_return_pct: float
    nifty_return_pct: float
    alpha_pct: float
    note: str


def _cumulative(returns: list[float]) -> float:
    return math.prod(1 + r for r in returns) - 1


async def benchmark_vs_nifty(db: AsyncSession) -> Benchmark | None:
    values = list(
        reversed(
            (
                await db.execute(
                    select(Snapshot.total_value)
                    .where(Snapshot.status == SnapshotStatus.OK.value)
                    .order_by(Snapshot.id.desc())
                    .limit(120)
                )
            )
            .scalars()
            .all()
        )
    )
    port = [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1]
    ]
    if len(port) < _MIN_DAYS:
        return None

    nifty = await _nifty_daily_returns()
    m = min(len(port), len(nifty))
    if m < _MIN_DAYS:
        return None  # NIFTY data unavailable

    p_cum = _cumulative(port[-m:])
    n_cum = _cumulative(nifty[-m:])
    return Benchmark(
        days=m,
        portfolio_return_pct=round(p_cum * 100, 2),
        nifty_return_pct=round(n_cum * 100, 2),
        alpha_pct=round((p_cum - n_cum) * 100, 2),
        note="Over the last "
        f"{m} trading days. Portfolio series includes SIP inflows — an approximation.",
    )
