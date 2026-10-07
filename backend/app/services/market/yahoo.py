"""Yahoo Finance market-data provider (free, no API key, real NSE data).

Uses the public v8 chart endpoint (one request per symbol, run concurrently).
Unlike the stocks-only community API, Yahoo also exposes NSE indices, so index
quotes are real here (``index_is_fixture`` is False). Any symbol that fails to
resolve is skipped, so the provider degrades gracefully.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.schemas.kite import IndexQuote
from app.services.market.base import BaseMarketDataProvider, SymbolQuote

logger = logging.getLogger("wealthpilot.market")

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Curated indices mapped to Yahoo symbols (display name -> yahoo symbol).
_INDICES: list[tuple[str, str]] = [
    ("NIFTY 50", "^NSEI"),
    ("NIFTY BANK", "^NSEBANK"),
    ("NIFTY ENERGY", "^CNXENERGY"),
    ("NIFTY METAL", "^CNXMETAL"),
]


class YahooMarketDataProvider(BaseMarketDataProvider):
    def __init__(self, timeout_seconds: float = 6.0, max_concurrency: int = 8) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://query1.finance.yahoo.com",
            timeout=timeout_seconds,
            headers={"User-Agent": _USER_AGENT},
        )
        self._sem = asyncio.Semaphore(max_concurrency)

    async def _fetch(self, yahoo_symbol: str) -> tuple[float, float] | None:
        """Return (last_price, change_pct) for a Yahoo symbol, or None on failure."""
        async with self._sem:
            try:
                resp = await self._client.get(
                    f"/v8/finance/chart/{yahoo_symbol}",
                    params={"interval": "1d", "range": "1d"},
                )
                resp.raise_for_status()
                meta = resp.json()["chart"]["result"][0]["meta"]
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                logger.warning("Yahoo fetch failed for %s: %s", yahoo_symbol, exc)
                return None

        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if not price or not prev:
            return None
        return float(price), round((float(price) - float(prev)) / float(prev) * 100, 2)

    async def get_index_quotes(self) -> list[IndexQuote]:
        results = await asyncio.gather(
            *(self._fetch(sym) for _name, sym in _INDICES)
        )
        quotes: list[IndexQuote] = []
        for (name, _sym), result in zip(_INDICES, results, strict=True):
            if result is None:
                continue
            price, change = result
            quotes.append(
                IndexQuote(name=name, last_price=round(price, 2), change_pct=change)
            )
        return quotes

    async def get_quotes(self, symbols: list[str]) -> list[SymbolQuote]:
        if not symbols:
            return []
        results = await asyncio.gather(*(self._fetch(f"{s}.NS") for s in symbols))
        quotes: list[SymbolQuote] = []
        for symbol, result in zip(symbols, results, strict=True):
            if result is None:
                continue
            price, change = result
            quotes.append(
                SymbolQuote(symbol=symbol, last_price=round(price, 2), change_pct=change)
            )
        return quotes

    async def _daily_returns(self, yahoo_symbol: str) -> list[float]:
        try:
            resp = await self._client.get(
                f"/v8/finance/chart/{yahoo_symbol}",
                params={"interval": "1d", "range": "3mo"},
            )
            resp.raise_for_status()
            result = resp.json()["chart"]["result"][0]
            raw = result["indicators"]["quote"][0]["close"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Yahoo history failed for %s: %s", yahoo_symbol, exc)
            return []
        closes = [float(c) for c in raw if c is not None]
        return [
            closes[i] / closes[i - 1] - 1.0
            for i in range(1, len(closes))
            if closes[i - 1]
        ]

    async def get_daily_returns(
        self, symbols: list[str], lookback_days: int = 90
    ) -> dict[str, list[float]]:
        if not symbols:
            return {}
        results = await asyncio.gather(*(self._daily_returns(f"{s}.NS") for s in symbols))
        return {s: r for s, r in zip(symbols, results, strict=True) if r}

    @property
    def index_is_fixture(self) -> bool:
        return False  # Yahoo provides real NSE indices

    async def close(self) -> None:
        await self._client.aclose()
