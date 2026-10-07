"""Phase 27 — NL → chart: build a renderable chart spec from live data.

Returns a small, frontend-agnostic spec ({type, title, series}) so Pilot can
answer "show my allocation as a donut" and the UI renders it. Every number is
from the latest snapshot — the model picks the chart, the data stays real.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import latest_holding_views
from app.services.goal_simulation import _sleeve_class

KINDS = ("allocation", "holdings", "pnl")


async def build_chart(db: AsyncSession, kind: str) -> dict[str, Any] | None:
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, cash = data
    kind = (kind or "allocation").lower()

    if kind in ("holdings", "top"):
        top = sorted(holdings, key=lambda h: h.value, reverse=True)[:8]
        return {
            "type": "bar",
            "title": "Top holdings by value",
            "series": [{"label": h.symbol, "value": round(h.value, 2)} for h in top],
        }
    if kind == "pnl":
        ordered = sorted(holdings, key=lambda h: h.pnl)
        picks = ordered[:4] + ordered[-4:]
        return {
            "type": "bar",
            "title": "P&L by holding",
            "series": [{"label": h.symbol, "value": round(h.pnl, 2)} for h in picks],
        }

    # default: allocation by asset class
    values: dict[str, float] = {}
    for h in holdings:
        cls = _sleeve_class(h)
        values[cls] = values.get(cls, 0.0) + h.value
    if cash:
        values["cash"] = cash
    return {
        "type": "donut",
        "title": "Allocation by asset class",
        "series": [
            {"label": k, "value": round(v, 2)}
            for k, v in sorted(values.items(), key=lambda x: -x[1])
        ],
    }
