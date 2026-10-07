"""Forward Monte Carlo projection of the whole portfolio (via the C++ engine).

Groups the latest snapshot's holdings into asset-class sleeves and asks the risk
engine to project total value forward month by month. Cash is treated as a
debt-like sleeve.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import latest_holding_views
from app.services.goal_simulation import (
    _DEFAULT_ASSUMPTION,
    RETURN_ASSUMPTIONS,
    _sleeve_class,
)
from app.services.risk import BaseRiskClient, ProjectionPoint, Sleeve

# Deterministic seed so repeated projections of the same portfolio are stable.
_PROJECTION_SEED = 42


async def portfolio_projection(
    db: AsyncSession,
    risk_client: BaseRiskClient,
    months: int,
    num_paths: int,
) -> list[ProjectionPoint] | None:
    """Project the portfolio forward, or None if there is no snapshot yet."""
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, cash = data

    sleeve_values: dict[str, float] = {}
    for holding in holdings:
        cls = _sleeve_class(holding)
        sleeve_values[cls] = sleeve_values.get(cls, 0.0) + holding.value
    if cash > 0:
        sleeve_values["debt"] = sleeve_values.get("debt", 0.0) + cash

    sleeves = [
        Sleeve(
            bucket=cls,
            value=round(value, 2),
            annual_return_mean=RETURN_ASSUMPTIONS.get(cls, _DEFAULT_ASSUMPTION)[0],
            annual_return_volatility=RETURN_ASSUMPTIONS.get(cls, _DEFAULT_ASSUMPTION)[1],
        )
        for cls, value in sorted(sleeve_values.items())
    ]

    return await risk_client.simulate_portfolio_projection(
        sleeves,
        monthly_contribution=0.0,
        months=months,
        num_paths=num_paths,
        seed=_PROJECTION_SEED,
    )
