"""Per-fund endpoints: list, order history, growth projection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.dependencies import DbSession, KiteDep, RiskDep
from app.schemas.analytics import ProjectionPointRead
from app.schemas.funds import FundRead, MFOrderRead
from app.services.funds_service import build_funds, fund_orders, fund_projection

router = APIRouter(prefix="/api/funds", tags=["funds"])


@router.get("", response_model=list[FundRead])
async def list_funds(db: DbSession) -> list[FundRead]:
    return await build_funds(db)


@router.get("/{isin}/orders", response_model=list[MFOrderRead])
async def fund_order_history(isin: str, kite: KiteDep) -> list[MFOrderRead]:
    orders = await fund_orders(kite, isin)
    return [MFOrderRead.model_validate(o) for o in orders]


@router.get("/{isin}/projection", response_model=list[ProjectionPointRead])
async def fund_growth_projection(
    isin: str,
    db: DbSession,
    risk: RiskDep,
    years: int = Query(default=10, ge=1, le=40),
) -> list[ProjectionPointRead]:
    points = await fund_projection(
        db, risk, isin, years * 12, get_settings().simulation_paths
    )
    if points is None:
        raise HTTPException(status_code=404, detail="Fund not found in latest snapshot.")
    return [ProjectionPointRead.model_validate(p) for p in points]
