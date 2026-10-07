"""Phase 51 — protective-put hedge sizing (heuristic).

Estimates how to hedge the equity-like exposure with NIFTY puts: how many lots
and roughly what premium, for a chosen protection level. No live options chain
(no free source), so the premium is a labelled rule-of-thumb — analysis to
inform, not a live quote.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

_NIFTY_LOT = 50
_PREMIUM_PCT = 0.015  # ~1.5% for a ~1-month, mildly-OTM index put (rule of thumb)


async def hedge_analysis(db: AsyncSession, protect_pct: float = 0.10) -> dict[str, Any] | None:
    from app.services.ai.xray import portfolio_xray
    from app.services.market import build_market_data_provider

    x = await portfolio_xray(db)
    if x is None:
        return None
    equity_like = sum(
        c["total"] for c in x["classes"] if c["asset_class"] in ("equity", "dividend")
    )
    if equity_like <= 0:
        return {"equity_exposure": 0.0, "message": "No equity-like exposure to hedge."}

    nifty_spot = 0.0
    provider = build_market_data_provider()
    try:
        for q in await provider.get_index_quotes():
            if "NIFTY 50" in q.name:
                nifty_spot = q.last_price
    except Exception:  # noqa: BLE001
        pass
    finally:
        await provider.close()

    lots = round(equity_like / (nifty_spot * _NIFTY_LOT)) if nifty_spot else 0
    est_premium = round(equity_like * _PREMIUM_PCT, 2)
    return {
        "equity_exposure": round(equity_like, 2),
        "protect_pct": round(protect_pct * 100, 1),
        "nifty_spot": round(nifty_spot, 2),
        "nifty_put_lots": lots,
        "est_premium_cost": est_premium,
        "note": (
            f"To cap a >{protect_pct * 100:.0f}% drop on ~₹{equity_like:,.0f} of equity-like "
            f"exposure, ~{lots} NIFTY put lot(s) ≈ ₹{est_premium:,.0f} premium "
            f"(~{_PREMIUM_PCT * 100:.1f}% rule of thumb, not a live quote)."
        ),
    }
