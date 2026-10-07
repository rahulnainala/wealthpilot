"""A ticker that polls a market-data provider and emits ticks.

Gives real (poll-based) live prices for held stocks without a WebSocket upstream,
so the live UI works on Zerodha's free tier via a third-party quote source.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

from app.services.market.base import BaseMarketDataProvider
from app.services.ticker.base import BaseTickerService, Tick, TickCallback

logger = logging.getLogger("wealthpilot.ticker")


class PollingTickerService(BaseTickerService):
    def __init__(
        self,
        provider: BaseMarketDataProvider,
        symbols: list[str],
        interval_seconds: float,
        include_indices: bool = True,
    ) -> None:
        self._provider = provider
        self._symbols = symbols
        self._interval = interval_seconds
        self._include_indices = include_indices
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self, on_tick: TickCallback) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(on_tick))

    async def _run(self, on_tick: TickCallback) -> None:
        while self._running:
            try:
                quotes = await self._provider.get_quotes(self._symbols)
                for quote in quotes:
                    await on_tick(
                        Tick(
                            instrument_token=0,
                            symbol=quote.symbol,
                            last_price=quote.last_price,
                            change_pct=quote.change_pct,
                            ts=time.time(),
                        )
                    )
                if self._include_indices:
                    for index in await self._provider.get_index_quotes():
                        await on_tick(
                            Tick(
                                instrument_token=index.instrument_token,
                                symbol=index.name,
                                last_price=index.last_price,
                                change_pct=index.change_pct,
                                ts=time.time(),
                            )
                        )
            except Exception as exc:  # noqa: BLE001 - polling must survive failures
                logger.warning("Polling ticker error: %s", exc)
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._provider.close()
