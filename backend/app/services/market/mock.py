"""Mock market-data provider backed by fixtures (offline/CI default)."""

from __future__ import annotations

import random

from app.schemas.kite import IndexQuote
from app.services.kite import fixtures
from app.services.market.base import BaseMarketDataProvider, SymbolQuote


class MockMarketDataProvider(BaseMarketDataProvider):
    async def get_index_quotes(self) -> list[IndexQuote]:
        return fixtures.mock_index_quotes()

    async def get_quotes(self, symbols: list[str]) -> list[SymbolQuote]:
        wanted = {s.upper() for s in symbols}
        quotes: list[SymbolQuote] = []
        for holding in fixtures.mock_holdings():
            if holding.tradingsymbol.upper() in wanted:
                quotes.append(
                    SymbolQuote(
                        symbol=holding.tradingsymbol,
                        last_price=holding.last_price,
                        change_pct=holding.pnl_pct,
                    )
                )
        return quotes

    async def get_daily_returns(
        self, symbols: list[str], lookback_days: int = 90
    ) -> dict[str, list[float]]:
        # Deterministic synthetic daily returns (~1.5% daily vol) per symbol.
        out: dict[str, list[float]] = {}
        for symbol in symbols:
            rng = random.Random(hash(symbol) & 0xFFFF)
            out[symbol] = [rng.gauss(0.0004, 0.015) for _ in range(60)]
        return out

    @property
    def index_is_fixture(self) -> bool:
        return True
