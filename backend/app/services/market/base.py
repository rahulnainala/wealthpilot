"""Market-data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.kite import IndexQuote


@dataclass(frozen=True)
class SymbolQuote:
    symbol: str
    last_price: float
    change_pct: float


class BaseMarketDataProvider(ABC):
    """Supplies index quotes and per-stock quotes from some upstream source."""

    @abstractmethod
    async def get_index_quotes(self) -> list[IndexQuote]:
        """Curated index/sector quotes (may be fixtures if the source lacks them)."""

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> list[SymbolQuote]:
        """Last price + day % change for each requested stock symbol."""

    @property
    @abstractmethod
    def index_is_fixture(self) -> bool:
        """True when index quotes are placeholder data, not a real feed."""

    async def get_daily_returns(
        self, symbols: list[str], lookback_days: int = 90
    ) -> dict[str, list[float]]:
        """Recent daily returns per symbol (empty when the source has none)."""
        return {}

    async def close(self) -> None:
        """Release any resources (no-op by default)."""
        return None
