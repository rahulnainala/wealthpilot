"""Phase 54: backtest the +10% take-profit sell rule against real price history.

The sell-off plan trims each legacy position once it is +10% in profit (else a
forced exit near the deadline in app.domain.exit_plan). This replays that
take-profit rule on
each legacy stock's actual Yahoo price path over a lookback window and compares
it to simply buying and holding.

Honesty note: purchase dates aren't stored, so the backtest assumes a
*hypothetical entry at the window's start* — it evaluates the rule as a strategy
on the price series, not against the owner's real cost basis. It answers "does a
+10% take-profit beat buy-and-hold on these names?", not "what was my P&L?".
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import select

from app.domain.enums import HoldingType
from app.models.goal import Goal
from app.services.analytics_service import latest_holding_views

logger = logging.getLogger(__name__)

_YAHOO_BASE = "https://query1.finance.yahoo.com"


async def _closes(client: httpx.AsyncClient, symbol: str, window: str) -> list[float]:
    """Daily closes for an NSE symbol over the window, oldest first."""
    try:
        resp = await client.get(
            f"/v8/finance/chart/{symbol}.NS",
            params={"interval": "1d", "range": window},
        )
        resp.raise_for_status()
        raw = resp.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Yahoo backtest history failed for %s: %s", symbol, exc)
        return []
    return [float(c) for c in raw if c is not None]


def _simulate(closes: list[float], threshold_pct: float) -> dict | None:
    """Take-profit vs buy-and-hold on one price series (entry = first close)."""
    if len(closes) < 2:
        return None
    entry = closes[0]
    if entry <= 0:
        return None
    target = entry * (1 + threshold_pct / 100)

    trigger_index: int | None = None
    for i, close in enumerate(closes):
        if close >= target:
            trigger_index = i
            break

    buy_hold_pct = (closes[-1] / entry - 1) * 100
    if trigger_index is not None:
        rule_pct = threshold_pct  # realized exactly at the take-profit level
        triggered = True
    else:
        # Never hit the threshold — the rule holds to the end, same as buy-and-hold.
        rule_pct = buy_hold_pct
        triggered = False

    return {
        "triggered": triggered,
        "days_to_trigger": trigger_index,
        "rule_return_pct": round(rule_pct, 2),
        "buy_hold_return_pct": round(buy_hold_pct, 2),
        # Positive = the take-profit rule beat holding (it sold before a decline).
        "edge_pct": round(rule_pct - buy_hold_pct, 2),
    }


async def backtest_sell_rule(db, threshold_pct: float = 10.0, window: str = "2y") -> dict:
    """Backtest the +10% take-profit rule across the legacy (unassigned) stocks."""
    loaded = await latest_holding_views(db)
    holdings = loaded[0] if loaded is not None else []
    goals = list((await db.execute(select(Goal).order_by(Goal.id))).scalars())

    claimed: set[str] = set()
    for goal in goals:
        claimed.update(goal.assigned_isins)

    legacy = [
        h for h in holdings if h.symbol not in claimed and h.type == HoldingType.STOCK
    ]
    if not legacy:
        return {
            "window": window,
            "threshold_pct": threshold_pct,
            "results": [],
            "message": "No legacy stock positions to backtest.",
        }

    async with httpx.AsyncClient(
        base_url=_YAHOO_BASE, timeout=8.0, headers={"User-Agent": "Mozilla/5.0"}
    ) as client:
        series = await asyncio.gather(
            *(_closes(client, h.symbol, window) for h in legacy)
        )

    results = []
    for h, closes in zip(legacy, series, strict=True):
        sim = _simulate(closes, threshold_pct)
        if sim is None:
            continue
        results.append({"symbol": h.symbol, "name": h.name or h.symbol, **sim})

    if not results:
        return {
            "window": window,
            "threshold_pct": threshold_pct,
            "results": [],
            "message": "No price history available for the legacy stocks.",
        }

    triggered = [r for r in results if r["triggered"]]
    avg_rule = sum(r["rule_return_pct"] for r in results) / len(results)
    avg_hold = sum(r["buy_hold_return_pct"] for r in results) / len(results)
    wins = sum(1 for r in results if r["edge_pct"] > 0)

    return {
        "window": window,
        "threshold_pct": threshold_pct,
        "count": len(results),
        "triggered_count": len(triggered),
        "avg_rule_return_pct": round(avg_rule, 2),
        "avg_buy_hold_return_pct": round(avg_hold, 2),
        "avg_edge_pct": round(avg_rule - avg_hold, 2),
        "rule_wins": wins,
        "results": sorted(results, key=lambda r: r["edge_pct"], reverse=True),
        "note": (
            f"Take-profit at +{threshold_pct:.0f}% vs buy-and-hold over {window}, "
            "assuming a hypothetical entry at the window's start (not your real "
            "cost basis). Positive edge = selling at the threshold beat holding."
        ),
    }
