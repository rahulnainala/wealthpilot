"""Phase 28 — nightly action agent.

Chains the tool layer (watch → optimize → tax) into one ranked "do this today"
plan, so all the intelligence lands as a short to-do instead of scattered
signals. Stored in the settings KV (no migration) and refreshed by the nightly
run, which also pushes the top action. Every item is engine/DB-cited; nothing
is executed.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import Setting
from app.services.risk import BaseRiskClient

_PLAN_KEY = "ai.daily_plan"
_RANK = {"action": 0, "watch": 1, "info": 2}
_VOL_DRIFT = 3.0  # est-vol gap (pts) that makes a rebalance worth surfacing


async def build_daily_plan(db: AsyncSession, risk_client: BaseRiskClient) -> list[dict]:
    """Assemble the ranked action list (most urgent first)."""
    from app.services.ai.optimize import optimize_portfolio
    from app.services.ai.tax import tax_summary
    from app.services.ai.watch import evaluate_watch

    items: list[dict] = []

    for a in await evaluate_watch(db, risk_client):
        items.append({"severity": a.severity, "title": a.text})

    opt = await optimize_portfolio(db)
    if opt and (opt.current_vol_est - opt.target_vol_est) >= _VOL_DRIFT:
        items.append({
            "severity": "info",
            "title": f"Rebalance toward risk parity — estimated volatility "
                     f"{opt.current_vol_est}% → {opt.target_vol_est}%.",
        })

    tax = await tax_summary(db)
    if tax and tax.harvest_candidates:
        loss = sum(h["loss"] for h in tax.harvest_candidates)
        items.append({
            "severity": "info",
            "title": f"Tax-loss harvest available: {len(tax.harvest_candidates)} holdings, "
                     f"₹{abs(loss):,.0f} of losses to offset gains.",
        })

    items.sort(key=lambda x: _RANK.get(x["severity"], 9))
    return items[:6]


async def build_and_store_plan(db: AsyncSession, risk_client: BaseRiskClient) -> list[dict]:
    items = await build_daily_plan(db, risk_client)
    payload = {"date": date.today().isoformat(), "items": items}
    row = (await db.execute(select(Setting).where(Setting.key == _PLAN_KEY))).scalar_one_or_none()
    if row is None:
        db.add(Setting(key=_PLAN_KEY, value=payload))
    else:
        row.value = payload
    await db.commit()
    return items


async def get_stored_plan(db: AsyncSession) -> dict:
    row = (await db.execute(select(Setting).where(Setting.key == _PLAN_KEY))).scalar_one_or_none()
    return row.value if row and isinstance(row.value, dict) else {"date": None, "items": []}
