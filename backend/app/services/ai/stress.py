"""Phase 32 — sector-aware scenario stress lab.

Applies differentiated shocks by sector (a crude shock hits PSU-energy harder
than gold) and reports the portfolio impact + hardest-hit holdings. Reuses the
existing PSU_ENERGY_CLUSTER and asset-class mapping; richer than the flat
goal-sim shock. Estimates for exploration, not predictions.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.issues import PSU_ENERGY_CLUSTER
from app.analytics.models import HoldingView
from app.services.analytics_service import latest_holding_views
from app.services.goal_simulation import _sleeve_class

_ENERGY_EXTRA = frozenset({"GAIL", "NTPC", "OIL", "HINDPETRO", "POWERGRID", "IGL", "PETRONET"})
_METALS = frozenset(
    {"NMDC", "HINDZINC", "SAIL", "VEDL", "JSWSTEEL", "TATASTEEL", "NATIONALUM", "HINDALCO"}
)

SCENARIOS: dict[str, dict[str, Any]] = {
    "energy": {
        "label": "Crude / energy shock",
        "energy": -0.20,
        "metal": -0.08,
        "equity": -0.05,
        "dividend": -0.05,
    },
    "market": {
        "label": "Broad market crash",
        "equity": -0.25,
        "dividend": -0.22,
        "energy": -0.28,
        "metal": -0.30,
        "gold": -0.05,
    },
    "rates": {"label": "Interest-rate spike", "debt": -0.05, "equity": -0.08, "dividend": -0.06},
    "gold": {"label": "Gold rally", "gold": 0.15},
}


def _sector(symbol: str, holding: HoldingView) -> str:
    sym = symbol.upper()
    if sym in PSU_ENERGY_CLUSTER or sym in _ENERGY_EXTRA:
        return "energy"
    if sym in _METALS:
        return "metal"
    return _sleeve_class(holding)


async def run_stress(db: AsyncSession, scenario: str) -> dict[str, Any] | None:
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, cash = data
    total = sum(h.value for h in holdings) + cash
    if total <= 0:
        return None

    sc = SCENARIOS.get(scenario, SCENARIOS["market"])
    total_after = cash
    hits: list[dict[str, Any]] = []
    for h in holdings:
        shock = sc.get(_sector(h.symbol, h), 0.0)
        after = h.value * (1 + shock)
        total_after += after
        if shock:
            hits.append(
                {
                    "symbol": h.symbol,
                    "shock": round(shock * 100, 1),
                    "change": round(after - h.value, 2),
                }
            )

    drop = total_after - total
    hits.sort(key=lambda x: x["change"])
    return {
        "label": sc["label"],
        "total_before": round(total, 2),
        "total_after": round(total_after, 2),
        "change": round(drop, 2),
        "change_pct": round(drop / total * 100, 2),
        "top_hits": hits[:6],
    }
