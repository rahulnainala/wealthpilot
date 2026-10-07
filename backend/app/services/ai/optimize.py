"""Phase 19 — portfolio optimization (inverse-volatility risk parity).

A full mean-variance QP in the C++ engine is high-effort/risk; this delivers the
same user value in Python using the SAME per-asset-class return/vol assumptions
the goal engine already uses (`RETURN_ASSUMPTIONS`). Inverse-volatility weighting
is a standard, solver-free risk-parity proxy: overweight the calmer classes so
risk is shared more evenly. Output is a suggested rebalance (current → target
with ₹ deltas) and an estimated volatility change — a recommendation to review,
never an executed trade.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import latest_holding_views
from app.services.goal_simulation import (
    _DEFAULT_ASSUMPTION,
    RETURN_ASSUMPTIONS,
    _sleeve_class,
)


@dataclass(frozen=True)
class OptimizeResult:
    method: str
    current: list[dict]        # {"asset_class", "weight", "value"}
    target: list[dict]         # {"asset_class", "weight"}
    rebalance: list[dict]      # {"asset_class", "delta_weight", "delta_amount"}
    current_vol_est: float     # weighted-avg volatility proxy (%)
    target_vol_est: float


async def optimize_portfolio(db: AsyncSession) -> OptimizeResult | None:
    """Suggest an inverse-vol risk-parity rebalance across asset classes."""
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, _cash = data

    values: dict[str, float] = {}
    for h in holdings:
        cls = _sleeve_class(h)
        values[cls] = values.get(cls, 0.0) + h.value
    total = sum(values.values())
    if total <= 0 or len(values) < 2:
        return None

    classes = sorted(values)
    vol = {c: RETURN_ASSUMPTIONS.get(c, _DEFAULT_ASSUMPTION)[1] for c in classes}
    current_w = {c: values[c] / total for c in classes}

    inv = {c: 1.0 / vol[c] for c in classes}
    inv_sum = sum(inv.values())
    target_w = {c: inv[c] / inv_sum for c in classes}

    # Correlation-agnostic proxy: weighted-average class volatility.
    cur_vol = sum(current_w[c] * vol[c] for c in classes)
    tgt_vol = sum(target_w[c] * vol[c] for c in classes)

    return OptimizeResult(
        method="inverse-volatility risk parity",
        current=[
            {"asset_class": c, "weight": round(current_w[c], 4), "value": round(values[c], 2)}
            for c in classes
        ],
        target=[{"asset_class": c, "weight": round(target_w[c], 4)} for c in classes],
        rebalance=[
            {
                "asset_class": c,
                "delta_weight": round(target_w[c] - current_w[c], 4),
                "delta_amount": round((target_w[c] - current_w[c]) * total, 2),
            }
            for c in classes
        ],
        current_vol_est=round(cur_vol * 100, 2),
        target_vol_est=round(tgt_vol * 100, 2),
    )
