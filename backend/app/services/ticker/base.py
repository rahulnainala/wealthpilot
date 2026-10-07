"""Ticker service interface and the Tick value object."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

# Called by a ticker for every incoming tick.
TickCallback = Callable[["Tick"], Awaitable[None]]


@dataclass(frozen=True)
class Tick:
    instrument_token: int
    symbol: str
    last_price: float
    change_pct: float
    ts: float  # epoch seconds

    def as_payload(self) -> dict[str, object]:
        return {
            "token": self.instrument_token,
            "symbol": self.symbol,
            "ltp": self.last_price,
            "change_pct": self.change_pct,
            "ts": self.ts,
        }


class BaseTickerService(ABC):
    """Produces ticks and forwards them to a supplied async callback."""

    @abstractmethod
    async def start(self, on_tick: TickCallback) -> None:
        """Begin streaming, invoking ``on_tick`` for each tick."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop streaming and release resources."""
