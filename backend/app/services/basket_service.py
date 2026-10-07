"""Target-allocation basket: per-bucket SIP routing + hold + legacy.

Encodes the investor's plan: new monthly SIP is routed to core index/flexicap
funds; ELSS is held (locked-in, no new money until the tax-regime call); the
Emergency Fund is near-cash, SIP + bonus-funded; legacy REIT/PSU positions get
no new money and are repositioned gradually. FI is paused — no new SIP until
Travel completes in 2030.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import SnapshotStatus
from app.models.goal import Goal
from app.models.snapshot import Snapshot, SnapshotHolding
from app.schemas.basket import (
    BasketPosition,
    BasketRead,
    BasketSleeve,
    LegacyHolding,
    MonthlySplit,
)

UTI, PARAG, NIPPON = "INF789F01XA0", "INF879O01027", "INF204KB18Z7"
HDFC_DEBT = "INF179K01YM7"
ZERODHA_ELSS, MIRAE_ELSS, GOLD = "INF0R8F01026", "INF769K01DM9", "HDFCGOLD"
# The Vehicle bucket's large-cap sleeve — note it is NOT the Zerodha ELSS
# above, despite the similar ISIN prefix.
ZERODHA_NIFTY50 = "INF0R8F01158"

SLEEVE_ROLES = {
    "travel": "Nearest deadline (2030) — biggest SIP share",
    "vehicle": "Vehicle (2031) — index + midcap, de-risk to arbitrage by 2030",
    "emergency": "Emergency fund — near-cash, SIP + bonus-funded",
    "fi": "Paused until 2030 — resumes once Travel completes and frees its SIP share",
}

# Per-bucket SIP routing: (label, symbol|None, share_of_bucket, mode, note).
Routing = tuple[str, str | None, float, str, str]
ROUTING: dict[str, list[Routing]] = {
    "travel": [
        ("UTI Nifty 50 Index", UTI, 0.60, "core", "Core large-cap index sleeve."),
        ("Parag Parikh Flexi Cap", PARAG, 0.40, "core", "Core growth (flexicap)."),
    ],
    "vehicle": [
        ("Nippon Nifty Midcap 150 Index", NIPPON, 0.50, "core", "Midcap sleeve."),
        (
            "Zerodha Nifty 50 Index",
            ZERODHA_NIFTY50,
            0.50,
            "core",
            "Large-cap sleeve — balances the midcap half of this bucket.",
        ),
    ],
    "emergency": [
        (
            "HDFC Short Term Debt",
            HDFC_DEBT,
            1.00,
            "core",
            "Near-cash / RD-arbitrage — monthly SIP (absorbs FI's paused share "
            "until 2030) plus any bonuses.",
        ),
    ],
    # FI is paused: no new SIP until Travel completes in 2030 and frees its
    # share — see the Retirement tab's
    # step-up model. Existing holdings are just held in the meantime.
    "fi": [
        (ZERODHA_ELSS, ZERODHA_ELSS, 0.0, "hold", "3-yr lock-in. Hold — no new money."),
        (MIRAE_ELSS, MIRAE_ELSS, 0.0, "hold", "3-yr lock-in. Hold — no new money."),
        (GOLD, GOLD, 0.0, "hold", "Small hedge — hold, don't add or remove."),
    ],
}

_LEGACY_NOTE = "Legacy — stop feeding; reposition gradually into core funds over 12–18mo."


async def _latest_holdings(db: AsyncSession) -> list[SnapshotHolding]:
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.status == SnapshotStatus.OK.value)
        .options(selectinload(Snapshot.holdings))
        .order_by(Snapshot.ts.desc(), Snapshot.id.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    return list(snapshot.holdings) if snapshot else []


def _sleeve(goal: Goal, members: dict[str, SnapshotHolding], total_value: float) -> BasketSleeve:
    current_value = round(sum(h.value for h in members.values()), 2)
    positions: list[BasketPosition] = []
    covered: set[str] = set()

    for label, symbol, weight, mode, note in ROUTING.get(goal.key, []):
        held = members.get(symbol) if symbol else None
        display = held.name if held and held.name else label
        if symbol:
            covered.add(symbol)
        positions.append(
            BasketPosition(
                label=display,
                symbol=symbol,
                current_value=round(held.value, 2) if held else 0.0,
                sip_pct=round(weight * 100, 1),
                sip_monthly=round(weight * goal.monthly_contribution, 2),
                mode=mode,
                note=note,
            )
        )

    # Any held-and-assigned holding not covered by the routing plan → hold.
    for symbol, held in members.items():
        if symbol in covered:
            continue
        positions.append(
            BasketPosition(
                label=held.name or symbol,
                symbol=symbol,
                current_value=round(held.value, 2),
                sip_pct=0.0,
                sip_monthly=0.0,
                mode="hold",
                note="Held — no routing rule set.",
            )
        )

    return BasketSleeve(
        goal_key=goal.key,
        goal_name=goal.name,
        role=SLEEVE_ROLES.get(goal.key, "Long-term holdings"),
        target_value=goal.target_value,
        current_value=current_value,
        monthly_contribution=goal.monthly_contribution,
        portfolio_pct=round(current_value / total_value * 100, 1) if total_value else 0.0,
        positions=positions,
    )


async def build_basket(db: AsyncSession) -> BasketRead:
    holdings = await _latest_holdings(db)
    goals = list((await db.execute(select(Goal).order_by(Goal.id))).scalars())
    total_value = round(sum(h.value for h in holdings), 2)

    # Claim each holding to at most one goal by explicit ISIN assignment.
    claimed: dict[str, Goal] = {}
    for goal in goals:
        for h in holdings:
            if h.symbol in goal.assigned_isins and h.symbol not in claimed:
                claimed[h.symbol] = goal

    sleeves: list[BasketSleeve] = []
    for goal in goals:
        members = {h.symbol: h for h in holdings if claimed.get(h.symbol) is goal}
        if not members and goal.key not in ROUTING:
            continue
        sleeves.append(_sleeve(goal, members, total_value))

    legacy = [
        LegacyHolding(
            symbol=h.symbol,
            name=h.name or h.symbol,
            current_value=round(h.value, 2),
            note=_LEGACY_NOTE,
        )
        for h in sorted(
            (h for h in holdings if h.symbol not in claimed),
            key=lambda x: x.value,
            reverse=True,
        )
    ]

    monthly_total = round(sum(g.monthly_contribution for g in goals), 2)
    monthly_split = [
        MonthlySplit(
            goal_name=g.name,
            monthly=g.monthly_contribution,
            pct=round(g.monthly_contribution / monthly_total * 100, 1) if monthly_total else 0.0,
        )
        for g in goals
        if g.monthly_contribution > 0
    ]

    return BasketRead(
        total_value=total_value,
        monthly_total=monthly_total,
        monthly_split=monthly_split,
        sleeves=sleeves,
        legacy=legacy,
    )
