"""Read-through caching decorator over any :class:`BaseKiteService`.

Wraps the five read methods in a shared process-level TTL cache so bursts of
dashboard traffic collapse to at most one upstream Kite call per resource per
TTL window. Auth methods pass straight through; a successful token exchange
invalidates the cache (a fresh login means fresh data).
"""

from __future__ import annotations

from app.schemas.kite import (
    Holding,
    IndexQuote,
    KiteTokenResponse,
    Margins,
    MFHolding,
    MFOrder,
    Position,
)
from app.services.cache import CacheBackend
from app.services.kite.base import BaseKiteService


class CachedKiteService(BaseKiteService):
    def __init__(
        self, inner: BaseKiteService, cache: CacheBackend, ttl_seconds: float
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl_seconds

    def get_login_url(self) -> str:
        return self._inner.get_login_url()

    def exchange_token(self, request_token: str) -> KiteTokenResponse:
        result = self._inner.exchange_token(request_token)
        self._cache.invalidate()
        return result

    async def get_holdings(self) -> list[Holding]:
        return await self._cache.get_or_set(
            "holdings", self._ttl, self._inner.get_holdings
        )

    async def get_mf_holdings(self) -> list[MFHolding]:
        return await self._cache.get_or_set(
            "mf_holdings", self._ttl, self._inner.get_mf_holdings
        )

    async def get_mf_orders(self) -> list[MFOrder]:
        return await self._cache.get_or_set(
            "mf_orders", self._ttl, self._inner.get_mf_orders
        )

    async def get_positions(self) -> list[Position]:
        return await self._cache.get_or_set(
            "positions", self._ttl, self._inner.get_positions
        )

    async def get_margins(self) -> Margins:
        return await self._cache.get_or_set(
            "margins", self._ttl, self._inner.get_margins
        )

    async def get_index_quotes(self) -> list[IndexQuote]:
        return await self._cache.get_or_set(
            "index_quotes", self._ttl, self._inner.get_index_quotes
        )

    async def place_gtt_sell(
        self, symbol: str, quantity: float, trigger_price: float, last_price: float
    ) -> str:
        return await self._inner.place_gtt_sell(symbol, quantity, trigger_price, last_price)
