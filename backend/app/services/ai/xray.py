"""Phase 33 — portfolio X-ray (asset-class look-through).

Mutual funds hide their asset class behind a single line; this aggregates true
equity/dividend/debt/gold exposure across everything and splits each class into
direct (stocks) vs via-funds. Class-level only — no stock-level composition feed
exists — but it reveals the real exposure behind the funds.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HoldingType
from app.services.analytics_service import latest_holding_views
from app.services.goal_simulation import _sleeve_class


async def portfolio_xray(db: AsyncSession) -> dict[str, Any] | None:
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, cash = data
    total = sum(h.value for h in holdings) + cash
    if total <= 0:
        return None

    buckets: dict[str, dict[str, float]] = {}
    for h in holdings:
        cls = _sleeve_class(h)
        key = "fund" if h.type == HoldingType.MF else "direct"
        buckets.setdefault(cls, {"direct": 0.0, "fund": 0.0})[key] += h.value
    if cash:
        buckets.setdefault("cash", {"direct": 0.0, "fund": 0.0})["direct"] += cash

    classes: list[dict[str, Any]] = [
        {
            "asset_class": cls,
            "direct": round(v["direct"], 2),
            "fund": round(v["fund"], 2),
            "total": round(v["direct"] + v["fund"], 2),
            "weight": round((v["direct"] + v["fund"]) / total, 4),
        }
        for cls, v in buckets.items()
    ]
    classes.sort(key=lambda x: -x["total"])
    return {"total": round(total, 2), "classes": classes}
