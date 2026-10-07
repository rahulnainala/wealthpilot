"""Phase 49 — external assets + net worth (beyond the Zerodha book)."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import CursorResult, select
from sqlalchemy import delete as sql_delete

from app.dependencies import DbSession
from app.models.external_asset import ExternalAsset
from app.models.liability import Liability

router = APIRouter(prefix="/api/assets", tags=["assets"])


class AssetCreate(BaseModel):
    name: str
    category: str
    value: float


class AssetRead(BaseModel):
    id: int
    name: str
    category: str
    value: float


class LiabilityCreate(BaseModel):
    name: str
    kind: str
    principal: float
    outstanding: float
    rate_pct: float | None = None
    emi: float | None = None
    start_date: date | None = None
    term_months: int | None = None


class LiabilityRead(LiabilityCreate):
    id: int


@router.get("", response_model=list[AssetRead])
async def list_assets(db: DbSession) -> list[AssetRead]:
    rows = (await db.execute(select(ExternalAsset).order_by(ExternalAsset.value.desc()))).scalars()
    return [AssetRead(id=a.id, name=a.name, category=a.category, value=a.value) for a in rows]


@router.get("/networth")
async def net_worth(db: DbSession) -> dict[str, Any]:
    """Net worth = Zerodha portfolio + external assets - liabilities.

    The subtraction is the point. This endpoint previously returned
    ``portfolio + external`` under the name "net worth", which is gross assets.
    With a large loan outstanding that is not a rounding difference — it is the
    wrong number, and the error grows with the debt.
    """
    from app.services.analytics_service import latest_holding_views

    data = await latest_holding_views(db)
    portfolio = (sum(h.value for h in data[0]) + data[1]) if data is not None else 0.0
    externals = (await db.execute(select(ExternalAsset))).scalars().all()
    ext_total = sum(a.value for a in externals)
    by_cat: dict[str, float] = {}
    for a in externals:
        by_cat[a.category] = by_cat.get(a.category, 0.0) + a.value
    by_cat["zerodha"] = round(portfolio, 2)
    liabilities = (await db.execute(select(Liability))).scalars().all()
    debt_total = sum(liability.outstanding for liability in liabilities)
    assets_total = portfolio + ext_total
    return {
        "portfolio": round(portfolio, 2),
        "external": round(ext_total, 2),
        "assets": round(assets_total, 2),
        "liabilities": round(debt_total, 2),
        "net_worth": round(assets_total - debt_total, 2),
        "by_category": {k: round(v, 2) for k, v in by_cat.items()},
        "by_liability": {
            liability.name: round(liability.outstanding, 2) for liability in liabilities
        },
    }


@router.get("/liabilities", response_model=list[LiabilityRead])
async def list_liabilities(db: DbSession) -> list[LiabilityRead]:
    rows = (
        await db.execute(select(Liability).order_by(Liability.outstanding.desc()))
    ).scalars()
    return [LiabilityRead.model_validate(r, from_attributes=True) for r in rows]


@router.post("/liabilities", response_model=LiabilityRead, status_code=201)
async def create_liability(payload: LiabilityCreate, db: DbSession) -> LiabilityRead:
    row = Liability(**payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return LiabilityRead.model_validate(row, from_attributes=True)


@router.delete("/liabilities/{liability_id}", status_code=204)
async def delete_liability(liability_id: int, db: DbSession) -> None:
    result = cast(
        "CursorResult[Any]",
        await db.execute(sql_delete(Liability).where(Liability.id == liability_id)),
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Liability not found")
    await db.commit()


@router.post("", response_model=AssetRead)
async def add_asset(payload: AssetCreate, db: DbSession) -> AssetRead:
    a = ExternalAsset(name=payload.name[:128], category=payload.category[:32], value=payload.value)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return AssetRead(id=a.id, name=a.name, category=a.category, value=a.value)


@router.delete("/{asset_id}")
async def delete_asset(asset_id: int, db: DbSession) -> dict[str, str]:
    res = cast(
        "CursorResult[Any]",
        await db.execute(sql_delete(ExternalAsset).where(ExternalAsset.id == asset_id)),
    )
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="not_found")
    return {"status": "deleted"}
