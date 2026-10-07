"""Tests for the connection hub: throttle, pruning, ticker lifecycle."""

from __future__ import annotations

from app.services.ticker.base import BaseTickerService, Tick, TickCallback
from app.services.ticker.hub import TickHub


class _NoopTicker(BaseTickerService):
    async def start(self, on_tick: TickCallback) -> None:
        return None

    async def stop(self) -> None:
        return None


class _FakeClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: dict[str, object]) -> None:
        self.sent.append(data)


class _DeadClient:
    async def send_json(self, data: dict[str, object]) -> None:
        raise RuntimeError("connection closed")


def _tick(token: int, symbol: str, ltp: float, ts: float) -> Tick:
    return Tick(instrument_token=token, symbol=symbol, last_price=ltp, change_pct=0.0, ts=ts)


async def test_throttles_to_one_per_second_per_symbol() -> None:
    hub = TickHub(_NoopTicker, throttle_seconds=1.0)
    client = _FakeClient()
    await hub.register(client)

    await hub.publish(_tick(1, "NIFTY 50", 100.0, ts=1000.0))  # sent
    await hub.publish(_tick(1, "NIFTY 50", 101.0, ts=1000.5))  # dropped (<1s)
    await hub.publish(_tick(1, "NIFTY 50", 102.0, ts=1001.5))  # sent (>1s)
    # A different symbol is not throttled by the first.
    await hub.publish(_tick(2, "NIFTY BANK", 500.0, ts=1000.6))  # sent

    ltps = [m["ltp"] for m in client.sent]
    assert ltps == [100.0, 102.0, 500.0]


async def test_prunes_dead_clients() -> None:
    hub = TickHub(_NoopTicker, throttle_seconds=0.0)
    good, dead = _FakeClient(), _DeadClient()
    await hub.register(good)
    await hub.register(dead)

    await hub.publish(_tick(1, "X", 100.0, ts=1.0))

    assert good.sent  # delivered
    assert hub.client_count == 1  # dead client pruned


async def test_ticker_lifecycle_tied_to_clients() -> None:
    calls = {"start": 0, "stop": 0}

    class _SpyTicker(BaseTickerService):
        async def start(self, on_tick: TickCallback) -> None:
            calls["start"] += 1

        async def stop(self) -> None:
            calls["stop"] += 1

    hub = TickHub(_SpyTicker)
    c1, c2 = _FakeClient(), _FakeClient()

    await hub.register(c1)
    assert hub.is_streaming and calls["start"] == 1
    await hub.register(c2)
    assert calls["start"] == 1  # not restarted for the second client

    await hub.unregister(c1)
    assert hub.is_streaming  # still one client
    await hub.unregister(c2)
    assert not hub.is_streaming and calls["stop"] == 1
