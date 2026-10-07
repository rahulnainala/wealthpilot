"""Phase 55: heuristic factor-exposure decomposition (value / momentum / quality / size).

This is a *proxy* decomposition, not a regression-based factor model — the app
has no fundamentals feed, so each holding is scored on transparent rules from
what is known (fund mandate keywords, stock type, trailing price momentum). The
portfolio exposure is the value-weighted average of those per-holding scores.
Scores are tilts in roughly [-1, +1]; size is signed (+ large-cap, − small-cap).
"""

from __future__ import annotations

import asyncio
import logging
import math

import httpx

from app.domain.enums import Bucket, HoldingType
from app.services.analytics_service import latest_holding_views

logger = logging.getLogger("wealthpilot.ai")

_YAHOO_BASE = "https://query1.finance.yahoo.com"

FACTOR_KEYS = ("value", "momentum", "quality", "size")


def _mf_scores(name: str) -> dict[str, float]:
    """Coarse factor tilts inferred from a fund's mandate keywords."""
    n = name.lower()
    # Non-equity sleeves carry ~no equity-factor exposure.
    if any(k in n for k in ("debt", "short term", "liquid", "arbitrage", "overnight", "gold")):
        return {"value": 0.0, "momentum": 0.0, "quality": 0.0, "size": 0.0}
    if any(k in n for k in ("nifty 50", "nifty50", "sensex", "large", "index")):
        return {"value": 0.1, "momentum": 0.0, "quality": 0.4, "size": 0.8}
    if any(k in n for k in ("mid cap", "midcap", "small cap", "smallcap", "nifty next")):
        return {"value": 0.1, "momentum": 0.2, "quality": -0.1, "size": -0.6}
    if "flexi" in n or "flex" in n or "multi" in n:
        return {"value": 0.0, "momentum": 0.1, "quality": 0.3, "size": 0.2}
    if "elss" in n:
        return {"value": 0.1, "momentum": 0.0, "quality": 0.2, "size": 0.3}
    # Generic active equity fund.
    return {"value": 0.0, "momentum": 0.0, "quality": 0.2, "size": 0.3}


def _stock_static_scores() -> dict[str, float]:
    """Base tilts for a directly-held stock (momentum filled in from prices).

    The legacy book is PSU/commodity/REIT — cyclical, dividend-paying value names
    that skew large-cap and lower on the quality (stability) axis.
    """
    return {"value": 0.6, "momentum": 0.0, "quality": -0.2, "size": 0.5}


async def _stock_momentum(client: httpx.AsyncClient, symbol: str) -> float:
    """~3-month trailing return squashed to a [-1, 1] momentum tilt."""
    try:
        resp = await client.get(
            f"/v8/finance/chart/{symbol}.NS",
            params={"interval": "1d", "range": "3mo"},
        )
        resp.raise_for_status()
        closes = resp.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.info("Momentum fetch skipped for %s (%s)", symbol, exc)
        return 0.0
    prices = [float(c) for c in closes if c is not None]
    if len(prices) < 2 or prices[0] <= 0:
        return 0.0
    trailing_return = prices[-1] / prices[0] - 1.0
    # tanh(scaled) keeps a ±30% move near the tilt extremes without clipping hard.
    return round(math.tanh(trailing_return * 4), 3)


async def factor_exposure(db) -> dict:
    """Value-weighted factor tilts across the whole equity book."""
    loaded = await latest_holding_views(db)
    holdings = loaded[0] if loaded is not None else []
    holdings = [h for h in holdings if h.value > 0]
    if not holdings:
        return {"factors": [], "message": "No holdings to decompose."}

    # Trailing momentum for directly-held stocks (fetched concurrently).
    stocks = [h for h in holdings if h.type == HoldingType.STOCK]
    momentum: dict[str, float] = {}
    if stocks:
        async with httpx.AsyncClient(
            base_url=_YAHOO_BASE, timeout=8.0, headers={"User-Agent": "Mozilla/5.0"}
        ) as client:
            moms = await asyncio.gather(
                *(_stock_momentum(client, h.symbol) for h in stocks)
            )
        momentum = {h.symbol: m for h, m in zip(stocks, moms, strict=True)}

    total = sum(h.value for h in holdings)
    sums = {k: 0.0 for k in FACTOR_KEYS}
    contributors: dict[str, list[tuple[str, float]]] = {k: [] for k in FACTOR_KEYS}

    for h in holdings:
        name = h.name or h.symbol
        is_gold = "gold" in name.lower() or "gold" in h.symbol.lower()
        if is_gold or h.bucket == Bucket.OTHER:  # gold / misc — no equity-factor tilt
            scores = {k: 0.0 for k in FACTOR_KEYS}
        elif h.type == HoldingType.STOCK:
            scores = _stock_static_scores()
            scores["momentum"] = momentum.get(h.symbol, 0.0)
        else:
            scores = _mf_scores(name)
        weight = h.value / total
        for k in FACTOR_KEYS:
            sums[k] += weight * scores[k]
            if abs(scores[k]) > 0.05:
                contributors[k].append((name, round(weight * scores[k], 4)))

    factors = []
    for k in FACTOR_KEYS:
        top = sorted(contributors[k], key=lambda x: abs(x[1]), reverse=True)[:3]
        factors.append(
            {
                "factor": k,
                "exposure": round(sums[k], 3),
                "tilt": _label(k, sums[k]),
                "top_contributors": [{"name": n, "contribution": c} for n, c in top],
            }
        )

    return {
        "factors": factors,
        "note": (
            "Heuristic proxy tilts from fund mandates + stock momentum, "
            "value-weighted — not a regression factor model. Size is signed "
            "(+ large-cap, − small/mid)."
        ),
    }


def _label(factor: str, value: float) -> str:
    if abs(value) < 0.1:
        return "neutral"
    if factor == "size":
        return "large-cap tilt" if value > 0 else "small/mid-cap tilt"
    strength = "strong" if abs(value) >= 0.35 else "mild"
    return f"{strength} {factor} tilt" if value > 0 else f"low {factor}"
