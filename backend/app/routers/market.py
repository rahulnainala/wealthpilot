"""Curated market overview endpoint (portfolio-adjacent indices & sectors).

Sourced from the configured market-data provider (mock fixtures by default),
decoupled from Kite so it works without a Zerodha market-data subscription.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.market import IndexQuoteRead, MarketOverview
from app.services.market import build_market_data_provider

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview", response_model=MarketOverview)
async def overview() -> MarketOverview:
    provider = build_market_data_provider()
    try:
        quotes = await provider.get_index_quotes()
        is_fixture = provider.index_is_fixture
    finally:
        await provider.close()
    return MarketOverview(
        is_fixture=is_fixture,
        indices=[IndexQuoteRead.model_validate(q) for q in quotes],
    )
