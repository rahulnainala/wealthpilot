"""Correlation-based diversification & concentration (via the C++ engine).

Builds a per-holding return series (real Yahoo history for stocks, a modeled
series for funds) plus value weights, and asks the C++ engine for the
diversification ratio, effective holdings, and most-correlated pairs.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HoldingType
from app.services.analytics_service import latest_holding_views
from app.services.market import BaseMarketDataProvider
from app.services.portfolio_risk_service import _synthetic_returns, cached_daily_returns
from app.services.risk import (
    BaseRiskClient,
    DiversificationAsset,
    DiversificationOutcome,
)


async def portfolio_diversification(
    db: AsyncSession,
    provider: BaseMarketDataProvider,
    risk_client: BaseRiskClient,
) -> DiversificationOutcome | None:
    """Diversification of the latest snapshot, or None if <2 holdings."""
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, _cash = data
    if len(holdings) < 2:
        return None

    stock_symbols = [h.symbol for h in holdings if h.type == HoldingType.STOCK]
    yahoo_returns = await cached_daily_returns(provider, stock_symbols)

    assets = [
        DiversificationAsset(
            label=h.symbol if h.type == HoldingType.STOCK else (h.name or h.symbol),
            weight=h.value,
            returns=yahoo_returns.get(h.symbol) or _synthetic_returns(h),
        )
        for h in holdings
    ]
    return await risk_client.compute_diversification(assets)
