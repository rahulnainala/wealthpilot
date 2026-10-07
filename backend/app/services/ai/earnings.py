"""Phase 38 — earnings / corporate-action calendar.

Upcoming results (and dividend dates where present) per stock holding via
Yahoo's quoteSummary, which needs a crumb+cookie handshake. Best-effort: the
handshake and each symbol degrade to skipped on any failure, and the whole
result is cached to avoid hammering.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import HoldingType
from app.services.analytics_service import latest_holding_views
from app.services.cache import get_shared_cache

logger = logging.getLogger("wealthpilot.ai")

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_TTL_S = 6 * 3600


async def _fetch(symbols: list[str]) -> list[dict]:
    out: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=_UA, follow_redirects=True) as c:
            try:
                await c.get("https://fc.yahoo.com/")
            except httpx.HTTPError:
                pass
            crumb = (await c.get("https://query1.finance.yahoo.com/v1/test/getcrumb")).text
            if not crumb or len(crumb) > 40:
                return []
            for sym in symbols:
                try:
                    r = await c.get(
                        f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}.NS",
                        params={"modules": "calendarEvents", "crumb": crumb},
                    )
                    if r.status_code != 200:
                        continue
                    ce = r.json()["quoteSummary"]["result"][0].get("calendarEvents", {})
                    ed = (ce.get("earnings", {}) or {}).get("earningsDate") or []
                    date = ed[0].get("fmt") if ed else None
                    if date:
                        out.append({"symbol": sym, "earnings_date": date})
                except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
                    continue
    except httpx.HTTPError as exc:
        logger.info("earnings handshake failed: %s", exc)
        return []
    out.sort(key=lambda x: x["earnings_date"])
    return out


async def earnings_calendar(db: AsyncSession) -> list[dict]:
    data = await latest_holding_views(db)
    if data is None:
        return []
    symbols = [h.symbol for h in data[0] if h.type == HoldingType.STOCK][:12]
    if not symbols:
        return []

    async def _factory() -> list[dict]:
        return await _fetch(symbols)

    return await get_shared_cache().get_or_set("ai:earnings", _TTL_S, _factory)
