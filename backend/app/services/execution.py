"""Phase 42 — guarded order execution.

Turns a sell draft into a real Kite GTT, but only on explicit `confirm`; without
it, returns a dry-run preview. Every attempt (dry-run, placed, failed) is written
to `order_audit`. Callers gate this behind auth. This is the one place the app is
allowed to move money — deliberately narrow and logged.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order_audit import OrderAudit
from app.models.snapshot import Snapshot, SnapshotHolding, SnapshotStatus
from app.services.kite import BaseKiteService

logger = logging.getLogger("wealthpilot.execution")


async def _last_price(db: AsyncSession, symbol: str, fallback: float) -> float:
    snap_id = (
        await db.execute(
            select(Snapshot.id)
            .where(Snapshot.status == SnapshotStatus.OK.value)
            .order_by(Snapshot.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snap_id is None:
        return fallback
    row = (
        await db.execute(
            select(SnapshotHolding.last_price).where(
                SnapshotHolding.snapshot_id == snap_id,
                func.upper(SnapshotHolding.symbol) == symbol.upper(),
            )
        )
    ).scalar_one_or_none()
    return float(row) if row else fallback


async def execute_gtt_sell(
    db: AsyncSession, kite: BaseKiteService, symbol: str, confirm: bool
) -> dict:
    """Dry-run preview (confirm=False) or place the real GTT (confirm=True)."""
    from app.services.ai.order_draft import draft_sell_order

    draft = await draft_sell_order(db, symbol)
    if draft is None:
        return {"status": "error", "message": "That stock isn't held — nothing to place."}

    audit = OrderAudit(
        symbol=draft.symbol,
        side=draft.side,
        quantity=draft.quantity,
        trigger_price=draft.trigger_price,
        dry_run=not confirm,
        status="dry_run" if not confirm else "pending",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    preview = {
        "symbol": draft.symbol,
        "side": draft.side,
        "quantity": draft.quantity,
        "trigger_price": draft.trigger_price,
        "est_proceeds": draft.est_proceeds,
        "est_ltcg_tax": draft.est_ltcg_tax,
    }

    if not confirm:
        return {
            "status": "dry_run",
            "order": preview,
            "message": "Review this. Send confirm=true to place the real GTT in Zerodha.",
        }

    # SAFETY GUARD: real orders are only allowed in secured mode (APP_PASSWORD set,
    # i.e. behind login on the deployed app). This makes accidental real placement
    # from local/dev impossible even against a live Kite session.
    from app.security.app_auth import auth_enabled

    if not auth_enabled():
        audit.status = "blocked"
        audit.dry_run = False
        audit.detail = "real placement blocked: app auth (APP_PASSWORD) not enabled"
        await db.commit()
        return {
            "status": "blocked",
            "order": preview,
            "message": (
                "Real order placement is only allowed in secured mode. Set APP_PASSWORD "
                "(login) — blocked in local/dev to prevent accidental orders."
            ),
        }

    last_price = await _last_price(db, draft.symbol, draft.trigger_price)
    try:
        gtt_id = await kite.place_gtt_sell(
            draft.symbol, draft.quantity, draft.trigger_price, last_price
        )
        audit.status = "placed"
        audit.gtt_id = str(gtt_id)
        await db.commit()
        logger.info("GTT placed: %s %s -> %s", draft.symbol, draft.quantity, gtt_id)
        return {"status": "placed", "gtt_id": str(gtt_id), "order": preview}
    except Exception as exc:  # noqa: BLE001 — record + surface, never silently swallow
        audit.status = "failed"
        audit.detail = str(exc)[:512]
        await db.commit()
        logger.exception("GTT placement failed for %s", draft.symbol)
        return {"status": "failed", "message": str(exc), "order": preview}


async def basket_rebalance_preview(db: AsyncSession) -> dict:
    """Phase 43 — preview the trims to move toward the risk-parity target.

    Preview only: it lists which holdings to reduce and by how much (largest in
    each overweight class first). Placement stays the per-holding secured path —
    we deliberately do NOT auto-loop real orders.
    """
    from app.services.ai.optimize import optimize_portfolio
    from app.services.analytics_service import latest_holding_views
    from app.services.goal_simulation import _sleeve_class

    opt = await optimize_portfolio(db)
    data = await latest_holding_views(db)
    if opt is None or data is None:
        return {"trims": [], "message": "Need at least two asset classes to rebalance."}
    holdings, _cash = data

    trims: list[dict] = []
    for r in opt.rebalance:
        if r["delta_amount"] >= -500:  # only meaningful reductions
            continue
        remaining = -r["delta_amount"]
        for h in sorted(
            (h for h in holdings if _sleeve_class(h) == r["asset_class"]),
            key=lambda h: h.value,
            reverse=True,
        ):
            if remaining <= 0:
                break
            cut = min(h.value, remaining)
            trims.append(
                {"symbol": h.symbol, "asset_class": r["asset_class"], "reduce_by": round(cut, 2)}
            )
            remaining -= cut
    return {
        "trims": trims,
        "message": "Toward the risk-parity target. Review and place each yourself "
        "(secured mode) — no auto-execution.",
    }


_AUTO_KEY = "execution.auto_gtt"


async def get_auto_execute(db: AsyncSession) -> bool:
    from app.models.settings import Setting

    row = (await db.execute(select(Setting).where(Setting.key == _AUTO_KEY))).scalar_one_or_none()
    return bool(row.value) if row is not None else False


async def set_auto_execute(db: AsyncSession, on: bool) -> bool:
    from app.models.settings import Setting

    row = (await db.execute(select(Setting).where(Setting.key == _AUTO_KEY))).scalar_one_or_none()
    if row is None:
        db.add(Setting(key=_AUTO_KEY, value=bool(on)))
    else:
        row.value = bool(on)
    await db.commit()
    return bool(on)


async def run_auto_execute(db: AsyncSession, kite: BaseKiteService) -> dict:
    """Phase 44 — opt-in autonomous placement of +10% sells.

    OFF by default (kill-switch = set_auto_execute(False)). When ON, places a GTT
    for each stock at/past its +10% threshold that hasn't been placed yet — BUT
    every placement routes through execute_gtt_sell's guard, so it's blocked
    unless the app is in secured mode. Never fires in local/dev.
    """
    if not await get_auto_execute(db):
        return {"enabled": False, "placed": []}

    from app.domain.enums import HoldingType
    from app.services.analytics_service import latest_holding_views

    data = await latest_holding_views(db)
    if data is None:
        return {"enabled": True, "placed": []}
    holdings, _cash = data

    already = {
        s
        for (s,) in (
            await db.execute(
                select(OrderAudit.symbol).where(OrderAudit.status == "placed")
            )
        ).all()
    }
    placed: list[str] = []
    for h in holdings:
        if h.type == HoldingType.STOCK and h.pnl_pct >= 10 and h.symbol not in already:
            res = await execute_gtt_sell(db, kite, h.symbol, confirm=True)
            if res.get("status") == "placed":
                placed.append(h.symbol)
    return {"enabled": True, "placed": placed}


async def recent_audits(db: AsyncSession, limit: int = 20) -> list[OrderAudit]:
    rows = (
        await db.execute(select(OrderAudit).order_by(OrderAudit.id.desc()).limit(limit))
    ).scalars()
    return list(rows)
