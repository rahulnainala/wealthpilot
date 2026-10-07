"""Phase 42 — order execution endpoints (guarded, audited).

The only write path that places real orders. Dry-run by default; a real GTT is
placed only with confirm=true, behind auth, and every attempt is audit-logged.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import DbSession, KiteDep, RequireAuth

router = APIRouter(prefix="/api/execution", tags=["execution"])


class GttRequest(BaseModel):
    symbol: str
    confirm: bool = False


@router.post("/gtt")
async def place_gtt(
    payload: GttRequest, db: DbSession, kite: KiteDep, _: RequireAuth
) -> dict[str, Any]:
    """Dry-run (default) or place a real GTT sell for a held stock. Human-in-loop."""
    from app.services.execution import execute_gtt_sell

    return await execute_gtt_sell(db, kite, payload.symbol, payload.confirm)


class AutoToggle(BaseModel):
    enabled: bool


@router.get("/auto")
async def auto_status(db: DbSession, _: RequireAuth) -> dict[str, Any]:
    """Phase 44: is autonomous +10% auto-execute on?"""
    from app.services.execution import get_auto_execute

    return {"enabled": await get_auto_execute(db)}


@router.post("/auto")
async def auto_set(payload: AutoToggle, db: DbSession, _: RequireAuth) -> dict[str, Any]:
    """Toggle auto-execute (kill-switch). OFF by default; only fires in secured mode."""
    from app.services.execution import set_auto_execute

    return {"enabled": await set_auto_execute(db, payload.enabled)}


@router.get("/basket-preview")
async def basket_preview(db: DbSession, _: RequireAuth) -> dict[str, Any]:
    """Phase 43: preview the trims to reach the risk-parity target (no placement)."""
    from app.services.execution import basket_rebalance_preview

    return await basket_rebalance_preview(db)


class AuditRead(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: float
    trigger_price: float
    dry_run: bool
    status: str
    gtt_id: str | None
    at: str


@router.get("/audit", response_model=list[AuditRead])
async def audit_log(db: DbSession, _: RequireAuth) -> list[AuditRead]:
    """Recent order-placement attempts (dry-run + real)."""
    from app.services.execution import recent_audits

    return [
        AuditRead(
            id=a.id, symbol=a.symbol, side=a.side, quantity=a.quantity,
            trigger_price=a.trigger_price, dry_run=a.dry_run, status=a.status,
            gtt_id=a.gtt_id, at=a.created_at.isoformat(),
        )
        for a in await recent_audits(db)
    ]
