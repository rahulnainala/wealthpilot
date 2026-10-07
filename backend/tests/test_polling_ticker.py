"""Tests for the polling ticker (real prices via a market-data provider)."""

from __future__ import annotations

import asyncio

from app.schemas.kite import IndexQuote
from app.services.market.base import BaseMarketDataProvider, SymbolQuote
from app.services.ticker.base import Tick
from app.services.ticker.polling import PollingTickerService


class _FakeProvider(BaseMarketDataProvider):
    def __init__(self) -> None:
        self.closed = False

    async def get_index_quotes(self) -> list[IndexQuote]:
        return [IndexQuote(name="NIFTY 50", last_price=24500.0, change_pct=0.4)]

    async def get_quotes(self, symbols: list[str]) -> list[SymbolQuote]:
        return [SymbolQuote(symbol="IOC", last_price=142.0, change_pct=1.5)]

    @property
    def index_is_fixture(self) -> bool:
        return True

    async def close(self) -> None:
        self.closed = True


async def test_polling_emits_ticks_and_closes_provider() -> None:
    provider = _FakeProvider()
    ticker = PollingTickerService(provider, ["IOC"], interval_seconds=0.01)
    received: list[Tick] = []

    async def on_tick(tick: Tick) -> None:
        received.append(tick)

    await ticker.start(on_tick)
    await asyncio.sleep(0.05)
    await ticker.stop()

    symbols = {t.symbol for t in received}
    assert "IOC" in symbols  # stock tick
    assert "NIFTY 50" in symbols  # index tick streamed live too
    assert provider.closed is True
