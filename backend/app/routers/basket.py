"""Target-allocation basket endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import DbSession
from app.schemas.basket import BasketRead
from app.services.basket_service import build_basket

router = APIRouter(prefix="/api/basket", tags=["basket"])


@router.get("", response_model=BasketRead)
async def get_basket(db: DbSession) -> BasketRead:
    """Holdings mapped to goal sleeves with target weights and rebalance drift."""
    return await build_basket(db)
