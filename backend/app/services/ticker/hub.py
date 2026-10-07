"""Connection hub: fan out ticks to browser WebSocket clients.

Owns exactly one upstream ticker for all clients, started lazily when the first
client connects and stopped when the last leaves. Applies per-symbol backpressure
(at most one update/second/symbol) and prunes dead connections on send failure.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from app.services.ticker.base import BaseTickerService, Tick
from app.services.ticker.mock import MockTickerService


@runtime_checkable
class WSClient(Protocol):
    async def send_json(self, data: dict[str, object]) -> None: ...


TickerFactory = Callable[[], BaseTickerService]


class TickHub:
    def __init__(
        self, ticker_factory: TickerFactory, throttle_seconds: float = 1.0
    ) -> None:
        self._factory = ticker_factory
        self._clients: set[WSClient] = set()
        self._ticker: BaseTickerService | None = None
        self._last_sent: dict[str, float] = {}
        self._throttle = throttle_seconds
        self._lock = asyncio.Lock()

    def set_ticker_factory(self, factory: TickerFactory) -> None:
        """Swap the upstream ticker factory (applies on next (re)start)."""
        self._factory = factory

    async def register(self, client: WSClient) -> None:
        async with self._lock:
            self._clients.add(client)
            if self._ticker is None:
                self._ticker = self._factory()
                await self._ticker.start(self.publish)

    async def unregister(self, client: WSClient) -> None:
        async with self._lock:
            self._clients.discard(client)
            if not self._clients and self._ticker is not None:
                await self._ticker.stop()
                self._ticker = None
                self._last_sent.clear()

    async def publish(self, tick: Tick) -> None:
        """Throttle per symbol, then broadcast to all clients."""
        last = self._last_sent.get(tick.symbol)
        if last is not None and tick.ts - last < self._throttle:
            return  # too soon for this symbol — drop
        self._last_sent[tick.symbol] = tick.ts
        await self._broadcast(tick)

    async def _broadcast(self, tick: Tick) -> None:
        payload = tick.as_payload()
        dead: list[WSClient] = []
        for client in list(self._clients):
            try:
                await client.send_json(payload)
            except Exception:  # noqa: BLE001 - prune any client that errors
                dead.append(client)
        for client in dead:
            self._clients.discard(client)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def is_streaming(self) -> bool:
        return self._ticker is not None


# Process-wide hub; defaults to the always-available mock ticker.
tick_hub = TickHub(MockTickerService)
