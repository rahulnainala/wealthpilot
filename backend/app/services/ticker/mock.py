"""In-memory ticker that emits random-walk ticks from the fixture portfolio.

Lets the live UI be demonstrated without market hours or a Kite session.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import time

from app.services.kite import fixtures
from app.services.ticker.base import BaseTickerService, Tick, TickCallback


class MockTickerService(BaseTickerService):
    def __init__(self, interval: float = 0.25, step: float = 0.002) -> None:
        self._interval = interval
        self._step = step  # max per-tick fractional move
        self._task: asyncio.Task[None] | None = None
        self._running = False
        # token -> (symbol, base_price, current_price)
        self._state = {
            token: (symbol, base, base)
            for token, (symbol, base) in fixtures.ticker_seed().items()
        }

    async def start(self, on_tick: TickCallback) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(on_tick))

    async def _run(self, on_tick: TickCallback) -> None:
        while self._running:
            for token, (symbol, base, price) in list(self._state.items()):
                price = max(0.01, price * (1 + random.uniform(-self._step, self._step)))
                self._state[token] = (symbol, base, price)
                change_pct = round((price - base) / base * 100, 2) if base else 0.0
                await on_tick(
                    Tick(
                        instrument_token=token,
                        symbol=symbol,
                        last_price=round(price, 2),
                        change_pct=change_pct,
                        ts=time.time(),
                    )
                )
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
