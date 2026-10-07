"""Portfolio VaR/CVaR via the C++ engine's ComputePortfolioRisk RPC.

Builds a daily return series per bucket (value-weighted over its holdings) — real
Yahoo history for stocks, a modeled series for mutual funds (no free NAV history)
— and hands them to the C++ engine for historical VaR/CVaR + risk contributions.
"""

from __future__ import annotations

import math
import random
import zlib
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import HoldingView
from app.domain.enums import HoldingType
from app.services.analytics_service import latest_holding_views
from app.services.cache import get_shared_cache
from app.services.goal_simulation import (
    _DEFAULT_ASSUMPTION,
    RETURN_ASSUMPTIONS,
    _sleeve_class,
)
from app.services.market import BaseMarketDataProvider
from app.services.risk import BaseRiskClient, BucketRisk, PortfolioRiskOutcome

_TRADING_DAYS = 252
_RETURNS_TTL_S = 1800.0  # daily history moves once a day; 30 min is generous


async def cached_daily_returns(
    provider: BaseMarketDataProvider, symbols: list[str]
) -> dict[str, list[float]]:
    """Yahoo daily-return series, cached — the hottest external fan-out."""
    if not symbols:
        return {}
    key = "market:returns:" + ",".join(sorted(symbols))
    return await get_shared_cache().get_or_set(
        key, _RETURNS_TTL_S, lambda: provider.get_daily_returns(symbols)
    )
_SERIES_LEN = 60


def _synthetic_returns(holding: HoldingView) -> list[float]:
    """Deterministic daily returns from the holding's asset-class volatility."""
    annual_vol = RETURN_ASSUMPTIONS.get(_sleeve_class(holding), _DEFAULT_ASSUMPTION)[1]
    daily_vol = annual_vol / math.sqrt(_TRADING_DAYS)
    # zlib.crc32 is process-stable; Python's hash() is randomized per process,
    # which made synthetic series (and VaR) jitter across backend restarts.
    rng = random.Random(zlib.crc32(holding.symbol.encode()) & 0xFFFF)
    return [rng.gauss(0.0003, daily_vol) for _ in range(_SERIES_LEN)]


async def portfolio_risk(
    db: AsyncSession,
    provider: BaseMarketDataProvider,
    risk_client: BaseRiskClient,
    confidence: float = 0.95,
) -> PortfolioRiskOutcome | None:
    """Return VaR/CVaR for the latest snapshot, or None if there is none."""
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, _cash = data

    stock_symbols = [h.symbol for h in holdings if h.type == HoldingType.STOCK]
    yahoo_returns = await cached_daily_returns(provider, stock_symbols)

    by_bucket: dict[str, list[HoldingView]] = defaultdict(list)
    for holding in holdings:
        by_bucket[holding.bucket.value].append(holding)

    bucket_inputs: list[BucketRisk] = []
    for bucket, members in by_bucket.items():
        total = sum(h.value for h in members)
        if total <= 0:
            continue
        weighted = [
            (h.value / total, yahoo_returns.get(h.symbol) or _synthetic_returns(h))
            for h in members
        ]
        length = min(len(series) for _weight, series in weighted)
        if length == 0:
            continue
        bucket_series = [
            sum(weight * series[t] for weight, series in weighted) for t in range(length)
        ]
        bucket_inputs.append(
            BucketRisk(bucket=bucket, value=round(total, 2), returns=bucket_series)
        )

    if not bucket_inputs:
        return None
    return await risk_client.compute_portfolio_risk(bucket_inputs, confidence)
