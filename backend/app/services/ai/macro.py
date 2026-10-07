"""Phase 36 — macro dashboard.

Tracks a few macro indicators (rupee, crude, NIFTY, India VIX) from Yahoo and
ties crude to the portfolio's PSU-energy exposure — context for a book heavy in
energy. Best-effort: cached, and any indicator that fails to resolve is skipped.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cache import get_shared_cache

logger = logging.getLogger("wealthpilot.ai")

_INDICATORS = [
    ("Rupee (USD/INR)", "INR=X"),
    ("Brent crude", "BZ=F"),
    ("NIFTY 50", "^NSEI"),
    ("India VIX", "^INDIAVIX"),
]
_TTL_S = 600.0


async def _quote(client: httpx.AsyncClient, symbol: str) -> dict[str, Any] | None:
    try:
        resp = await client.get(
            f"/v8/finance/chart/{symbol}", params={"interval": "1d", "range": "1d"}
        )
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.info("macro fetch failed for %s: %s", symbol, exc)
        return None
    if not price or not prev:
        return None
    return {"price": round(float(price), 2), "change_pct": round((price - prev) / prev * 100, 2)}


async def _fetch_all() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(
        base_url="https://query1.finance.yahoo.com", timeout=8.0,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        results = await asyncio.gather(*(_quote(client, sym) for _n, sym in _INDICATORS))
    out: list[dict[str, Any]] = []
    for (name, sym), q in zip(_INDICATORS, results, strict=True):
        if q is not None:
            out.append({"name": name, "symbol": sym, **q})
    return out


async def _energy_exposure_pct(db: AsyncSession) -> float:
    from app.services.ai.stress import _sector
    from app.services.analytics_service import latest_holding_views

    data = await latest_holding_views(db)
    if data is None:
        return 0.0
    holdings, cash = data
    total = sum(h.value for h in holdings) + cash
    if total <= 0:
        return 0.0
    energy = sum(h.value for h in holdings if _sector(h.symbol, h) == "energy")
    return round(energy / total * 100, 1)


async def macro_dashboard(db: AsyncSession) -> dict[str, Any]:
    indicators = await get_shared_cache().get_or_set("ai:macro", _TTL_S, _fetch_all)
    energy = await _energy_exposure_pct(db)
    return {
        "indicators": indicators,
        "energy_exposure_pct": energy,
        "note": f"You hold {energy:.0f}% in PSU-energy — crude moves matter more than average.",
    }
