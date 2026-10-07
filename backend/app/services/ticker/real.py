"""Real Kite ticker: bridges KiteTicker's threaded callbacks into asyncio.

KiteTicker runs its own (Twisted) reactor thread and calls back synchronously,
so ticks are marshalled onto the app's event loop via
``run_coroutine_threadsafe``. Only used when ``USE_MOCK_KITE`` is false and a
live session exists; the mock ticker backs all tests and offline demos.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

from kiteconnect import KiteTicker

from app.services.ticker.base import BaseTickerService, Tick, TickCallback

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)


def is_market_open(now: datetime | None = None) -> bool:
    """True during NSE trading hours (09:15-15:30 IST, Mon-Fri)."""
    now = now or datetime.now(IST)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    return MARKET_OPEN <= now.timetz().replace(tzinfo=None) <= MARKET_CLOSE


class RealTickerService(BaseTickerService):
    def __init__(
        self,
        api_key: str,
        access_token: str,
        instrument_tokens: dict[int, str],
    ) -> None:
        self._api_key = api_key
        self._access_token = access_token
        self._tokens = instrument_tokens
        self._kws: KiteTicker | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._on_tick: TickCallback | None = None

    async def start(self, on_tick: TickCallback) -> None:
        self._loop = asyncio.get_running_loop()
        self._on_tick = on_tick
        kws = KiteTicker(self._api_key, self._access_token)
        kws.on_connect = self._on_connect
        kws.on_ticks = self._on_ticks
        self._kws = kws
        kws.connect(threaded=True)

    def _on_connect(self, ws: KiteTicker, response: object) -> None:
        tokens = list(self._tokens.keys())
        ws.subscribe(tokens)
        ws.set_mode(ws.MODE_QUOTE, tokens)  # QUOTE mode carries ohlc for % change

    async def _dispatch(self, tick: Tick) -> None:
        if self._on_tick is not None:
            await self._on_tick(tick)

    def _on_ticks(self, ws: KiteTicker, ticks: list[dict[str, object]]) -> None:
        if self._loop is None or self._on_tick is None:
            return
        for raw in ticks:
            tick = self._to_tick(raw)
            if tick is not None:
                asyncio.run_coroutine_threadsafe(self._dispatch(tick), self._loop)

    @staticmethod
    def _as_float(value: object) -> float:
        return float(value) if isinstance(value, (int, float)) else 0.0

    def _to_tick(self, raw: dict[str, object]) -> Tick | None:
        token = raw.get("instrument_token")
        if not isinstance(token, int):
            return None
        last_price = self._as_float(raw.get("last_price"))
        ohlc = raw.get("ohlc")
        close = self._as_float(ohlc.get("close")) if isinstance(ohlc, dict) else 0.0
        change_pct = round((last_price - close) / close * 100, 2) if close else 0.0
        return Tick(
            instrument_token=token,
            symbol=self._tokens.get(token, str(token)),
            last_price=last_price,
            change_pct=change_pct,
            ts=time.time(),
        )

    async def stop(self) -> None:
        if self._kws is not None:
            self._kws.close()
            self._kws = None
