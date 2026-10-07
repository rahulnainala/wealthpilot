"""Phase 34 — dividend income forecast.

Estimates annual dividend income from the dividend-bucket holdings (PSU-energy,
REITs) using a clearly-labelled assumed blended yield — per-symbol trailing
yield needs Yahoo's fragile quoteSummary, so we keep this reliable and honest.
Reports annual + monthly-average income for a rough cash-flow view.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import Bucket
from app.services.analytics_service import latest_holding_views

_ASSUMED_YIELD = 0.055  # blended assumption for the dividend bucket


async def dividend_forecast(db: AsyncSession) -> dict | None:
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, _cash = data

    items = [
        {
            "symbol": h.symbol,
            "annual": round(h.value * _ASSUMED_YIELD, 2),
            "value": round(h.value, 2),
        }
        for h in holdings
        if h.bucket == Bucket.DIVIDEND and h.value > 0
    ]
    items.sort(key=lambda x: -x["annual"])
    annual = round(sum(i["annual"] for i in items), 2)
    return {
        "assumed_yield_pct": round(_ASSUMED_YIELD * 100, 1),
        "annual_income": annual,
        "monthly_avg": round(annual / 12, 2),
        "holdings": items,
        "note": "Estimate at an assumed 5.5% blended yield on dividend-bucket holdings; "
        "actual payouts are lumpy and vary by company.",
    }
