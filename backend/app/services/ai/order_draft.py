"""Phase 12 — human-in-loop GTT sell-order drafting (READ-ONLY).

Given a legacy holding, compute the parameters of a GTT sell order the owner
would place to execute the +10% plan — symbol, quantity, trigger price, and how
the proceeds route (the plan's 50/30/20 split). This NEVER places an order; it only
drafts numbers for the owner to review and enter in Zerodha themselves. All
figures come from the latest snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snapshot import Snapshot, SnapshotHolding, SnapshotStatus

SELL_THRESHOLD = 1.10  # the +10% target
# Proceeds split (mirrors frontend PROCEEDS_SPLIT: Travel/Vehicle/Emergency).
_ROUTES = (("Travel", 0.50), ("Vehicle", 0.30), ("Emergency", 0.20))


@dataclass(frozen=True)
class OrderDraft:
    symbol: str
    side: str
    quantity: float
    trigger_price: float
    est_proceeds: float
    threshold_met: bool
    gain: float = 0.0
    est_ltcg_tax: float = 0.0
    routing: list[dict] = field(default_factory=list)
    note: str = ""


async def draft_sell_order(db: AsyncSession, symbol: str) -> OrderDraft | None:
    """Draft a GTT sell for a held stock; None if not currently held."""
    snap_id = (
        await db.execute(
            select(Snapshot.id)
            .where(Snapshot.status == SnapshotStatus.OK.value)
            .order_by(Snapshot.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if snap_id is None:
        return None

    # Query the holding row directly — avoids a lazy relationship load in async.
    want = symbol.strip().upper()
    holding = (
        await db.execute(
            select(SnapshotHolding).where(
                SnapshotHolding.snapshot_id == snap_id,
                func.upper(SnapshotHolding.symbol) == want,
            )
        )
    ).scalar_one_or_none()
    if holding is None or holding.qty <= 0:
        return None

    trigger = round(holding.avg_price * SELL_THRESHOLD, 2)
    threshold_met = holding.last_price >= trigger
    # Once the target is met, a realistic trigger sits just under the live price.
    if threshold_met:
        trigger = round(holding.last_price, 2)
    est = round(holding.qty * trigger, 2)
    gain = round((trigger - holding.avg_price) * holding.qty, 2)
    from app.services.ai.tax import estimate_ltcg_tax

    est_tax = estimate_ltcg_tax(gain)
    routing = [{"label": label, "amount": round(est * share, 2)} for label, share in _ROUTES]
    note = (
        "Threshold already met — place at market or a GTT just below the live price."
        if threshold_met
        else f"GTT triggers a SELL when {holding.symbol} reaches the +10% target."
    )
    return OrderDraft(
        symbol=holding.symbol,
        side="SELL",
        quantity=holding.qty,
        trigger_price=trigger,
        est_proceeds=est,
        threshold_met=threshold_met,
        gain=gain,
        est_ltcg_tax=est_tax,
        routing=routing,
        note=note + " Review and place it yourself in Zerodha — Pilot never executes orders.",
    )
