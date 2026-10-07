"""Helpers to build pure analytics inputs from the mock fixture portfolio."""

from __future__ import annotations

from app.analytics.buckets import classify_mutual_fund, classify_stock
from app.analytics.models import HoldingView
from app.domain.enums import HoldingType
from app.services.kite import fixtures

MOCK_CASH = fixtures.MOCK_CASH


def mock_holding_views() -> list[HoldingView]:
    """The fictional fixture portfolio as pure HoldingView objects."""
    views: list[HoldingView] = []
    for h in fixtures.mock_holdings():
        views.append(
            HoldingView(
                symbol=h.tradingsymbol,
                bucket=classify_stock(h.tradingsymbol),
                type=HoldingType.STOCK,
                value=h.value,
                invested=h.invested,
                pnl=h.pnl,
                pnl_pct=h.pnl_pct,
            )
        )
    for m in fixtures.mock_mf_holdings():
        views.append(
            HoldingView(
                symbol=m.isin,
                bucket=classify_mutual_fund(),
                type=HoldingType.MF,
                value=m.value,
                invested=m.invested,
                pnl=m.pnl,
                pnl_pct=m.pnl_pct,
                name=m.fund,
            )
        )
    return views
