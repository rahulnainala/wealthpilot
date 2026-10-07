"""Per-fund views: holdings + audit metadata, order history, growth projection."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analytics.mf_audit import MF_AUDIT, mf_asset_class
from app.domain.enums import HoldingType, SnapshotStatus
from app.models.snapshot import Snapshot, SnapshotHolding
from app.schemas.funds import FundRead, GoalRef
from app.schemas.kite import MFOrder
from app.services.analytics_service import load_goal_views
from app.services.goal_simulation import _DEFAULT_ASSUMPTION, RETURN_ASSUMPTIONS
from app.services.kite import BaseKiteService
from app.services.risk import BaseRiskClient, ProjectionPoint, Sleeve


async def _latest_mf_holdings(db: AsyncSession) -> list[SnapshotHolding]:
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.status == SnapshotStatus.OK.value)
        .options(selectinload(Snapshot.holdings))
        .order_by(Snapshot.ts.desc(), Snapshot.id.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        return []
    return [h for h in snapshot.holdings if h.type == HoldingType.MF.value]


async def build_funds(db: AsyncSession) -> list[FundRead]:
    """List each held fund with audit metadata and the goals it's assigned to."""
    holdings = await _latest_mf_holdings(db)
    goals = await load_goal_views(db)

    funds: list[FundRead] = []
    for h in holdings:
        meta = MF_AUDIT.get(h.symbol)
        assigned = [
            GoalRef(key=g.key, name=g.name, target_value=g.target_value)
            for g in goals
            if h.symbol in g.assigned_isins
        ]
        funds.append(
            FundRead(
                isin=h.symbol,
                name=meta.name if meta else (h.name or h.symbol),
                category=meta.category if meta else "Mutual Fund",
                asset_class=meta.asset_class.value if meta else "equity",
                recommendation=meta.recommendation.value if meta else "keep",
                goal_tag=meta.goal_tag if meta else None,
                units=h.qty,
                avg_nav=h.avg_price,
                nav=h.last_price,
                invested=h.invested,
                value=h.value,
                pnl=h.pnl,
                assigned_goals=assigned,
            )
        )
    return funds


async def fund_orders(kite: BaseKiteService, isin: str) -> list[MFOrder]:
    """Order history for a single fund (most recent first)."""
    orders = [o for o in await kite.get_mf_orders() if o.isin == isin]
    return sorted(orders, key=lambda o: o.order_timestamp or "", reverse=True)


async def fund_projection(
    db: AsyncSession,
    risk_client: BaseRiskClient,
    isin: str,
    months: int,
    num_paths: int,
) -> list[ProjectionPoint] | None:
    """Forward Monte Carlo projection of a single fund's current value (C++)."""
    holding = next((h for h in await _latest_mf_holdings(db) if h.symbol == isin), None)
    if holding is None:
        return None

    asset_class = mf_asset_class(isin)
    cls = asset_class.value if asset_class else "equity"
    mean, vol = RETURN_ASSUMPTIONS.get(cls, _DEFAULT_ASSUMPTION)
    sleeve = Sleeve(
        bucket=cls,
        value=holding.value,
        annual_return_mean=mean,
        annual_return_volatility=vol,
    )
    return await risk_client.simulate_portfolio_projection(
        [sleeve], 0.0, months, num_paths, seed=hash(isin) & 0xFFFF
    )
