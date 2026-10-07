"""Tests for the mock ticker and the market-hours helper."""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.ticker.base import Tick
from app.services.ticker.mock import MockTickerService
from app.services.ticker.real import is_market_open

IST = ZoneInfo("Asia/Kolkata")


async def test_mock_ticker_emits_ticks() -> None:
    ticker = MockTickerService(interval=0.01)
    received: list[Tick] = []

    async def on_tick(tick: Tick) -> None:
        received.append(tick)

    await ticker.start(on_tick)
    await asyncio.sleep(0.05)
    await ticker.stop()

    assert received
    tick = received[0]
    assert tick.symbol
    assert tick.last_price > 0
    assert isinstance(tick.as_payload()["ltp"], float)


async def test_mock_ticker_start_is_idempotent() -> None:
    ticker = MockTickerService(interval=0.01)

    async def on_tick(tick: Tick) -> None:
        return None

    await ticker.start(on_tick)
    await ticker.start(on_tick)  # second start is a no-op
    await ticker.stop()


def test_market_hours() -> None:
    # Wednesday 10:00 IST -> open.
    assert is_market_open(datetime(2026, 7, 8, 10, 0, tzinfo=IST)) is True
    # Wednesday 16:00 IST -> closed.
    assert is_market_open(datetime(2026, 7, 8, 16, 0, tzinfo=IST)) is False
    # Sunday -> closed.
    assert is_market_open(datetime(2026, 7, 5, 10, 0, tzinfo=IST)) is False
