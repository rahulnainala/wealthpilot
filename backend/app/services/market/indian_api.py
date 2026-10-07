"""Free Indian-Stock-Market-API provider (stocks only; indices fall back).

Targets the community API documented at 0xramm/Indian-Stock-Market-API. It has
no index endpoints, so ``get_index_quotes`` returns fixtures — the real value is
``get_quotes`` for live per-stock prices, which powers the polling ticker on
Zerodha's free tier. All failures degrade gracefully (empty / fixtures).
"""

from __future__ import annotations

import logging

import httpx

from app.schemas.kite import IndexQuote
from app.services.kite import fixtures
from app.services.market.base import BaseMarketDataProvider, SymbolQuote

logger = logging.getLogger("wealthpilot.market")


class IndianApiMarketDataProvider(BaseMarketDataProvider):
    def __init__(self, base_url: str, timeout_seconds: float = 6.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url, timeout=timeout_seconds
        )

    async def get_index_quotes(self) -> list[IndexQuote]:
        # The upstream API exposes individual stocks only — no index feed.
        return fixtures.mock_index_quotes()

    async def get_quotes(self, symbols: list[str]) -> list[SymbolQuote]:
        if not symbols:
            return []
        try:
            response = await self._client.get(
                "/stock/list",
                params={"symbols": ",".join(symbols), "res": "num"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Market data fetch failed: %s", exc)
            return []

        quotes: list[SymbolQuote] = []
        for row in payload.get("stocks", []):
            symbol = row.get("symbol")
            if not symbol:
                continue
            quotes.append(
                SymbolQuote(
                    symbol=str(symbol),
                    last_price=float(row.get("last_price", 0.0) or 0.0),
                    change_pct=float(row.get("percent_change", 0.0) or 0.0),
                )
            )
        return quotes

    @property
    def index_is_fixture(self) -> bool:
        return True  # no real index feed upstream

    async def close(self) -> None:
        await self._client.aclose()
