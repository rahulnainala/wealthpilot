"""Phase 20 — tax-aware sell plan (FY 2025-26 equity regime).

Snapshots don't carry per-lot buy dates, so holding period is unknown; the +10%
plan targets long-held legacy stocks, so estimates DEFAULT to LTCG and clearly
say so, with STCG shown as the alternative. Also surfaces tax-loss-harvest
candidates (holdings sitting at a loss that could offset realized gains). These
are estimates to inform the owner, not tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HoldingType
from app.services.analytics_service import latest_holding_views

LTCG_RATE = 0.125          # 12.5% over the annual exemption
LTCG_EXEMPTION = 125_000.0  # ₹1.25 lakh per financial year
STCG_RATE = 0.20           # 20% on short-term equity gains


def estimate_ltcg_tax(gain: float, exemption_left: float = LTCG_EXEMPTION) -> float:
    """LTCG on an equity gain after applying the remaining annual exemption."""
    if gain <= 0:
        return 0.0
    taxable = max(0.0, gain - max(0.0, exemption_left))
    return round(taxable * LTCG_RATE, 2)


def estimate_stcg_tax(gain: float) -> float:
    return round(max(0.0, gain) * STCG_RATE, 2)


@dataclass(frozen=True)
class TaxSummary:
    total_unrealized_gain: float
    est_ltcg_tax: float          # if all gains realized this FY, long-term
    est_stcg_tax: float          # short-term alternative
    harvest_candidates: list[dict[str, Any]]  # {"symbol", "loss"} — losers that can offset
    note: str


async def tax_summary(db: AsyncSession) -> TaxSummary | None:
    """Portfolio-level tax read for the sell plan (stocks)."""
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, _cash = data
    stocks = [h for h in holdings if h.type == HoldingType.STOCK]
    gains = sum(h.pnl for h in stocks if h.pnl > 0)
    harvest = [
        {"symbol": h.symbol, "loss": round(h.pnl, 2)}
        for h in sorted((h for h in stocks if h.pnl < 0), key=lambda h: h.pnl)
    ]
    return TaxSummary(
        total_unrealized_gain=round(gains, 2),
        est_ltcg_tax=estimate_ltcg_tax(gains),
        est_stcg_tax=estimate_stcg_tax(gains),
        harvest_candidates=harvest,
        note=(
            "Assumes long-term holding (>12 months) — the usual case for legacy "
            "stocks. LTCG 12.5% over the ₹1.25L exemption; STCG 20% if held under "
            "a year. Estimates, not tax advice."
        ),
    )
