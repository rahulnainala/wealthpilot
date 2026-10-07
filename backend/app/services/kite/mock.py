"""In-memory Kite service seeded with fixture data.

Activated with ``USE_MOCK_KITE=true``. All development and tests run against
this so the app is fully functional offline, without a Kite session or market
hours.
"""

from __future__ import annotations

from app.schemas.kite import (
    Holding,
    IndexQuote,
    KiteTokenResponse,
    Margins,
    MFHolding,
    MFOrder,
    Position,
)
from app.services.kite import fixtures
from app.services.kite.base import BaseKiteService


class MockKiteService(BaseKiteService):
    """Deterministic Kite service backed by :mod:`app.services.kite.fixtures`."""

    def get_login_url(self) -> str:
        return "https://kite.zerodha.com/connect/login?v=3&api_key=mock-api-key"

    def exchange_token(self, request_token: str) -> KiteTokenResponse:
        # Echo the request_token back as a fake access token so the auth flow is
        # exercisable end-to-end without real Zerodha credentials.
        return KiteTokenResponse(
            access_token=f"mock-access-{request_token}",
            user_id="MOCK123",
            public_token=f"mock-public-{request_token}",
        )

    async def get_holdings(self) -> list[Holding]:
        return fixtures.mock_holdings()

    async def get_mf_holdings(self) -> list[MFHolding]:
        return fixtures.mock_mf_holdings()

    async def get_mf_orders(self) -> list[MFOrder]:
        return fixtures.mock_mf_orders()

    async def get_positions(self) -> list[Position]:
        return []  # no open F&O/intraday positions in the seed portfolio

    async def get_margins(self) -> Margins:
        return Margins(available_cash=fixtures.MOCK_CASH, net=fixtures.MOCK_CASH)

    async def get_index_quotes(self) -> list[IndexQuote]:
        return fixtures.mock_index_quotes()

    async def place_gtt_sell(
        self, symbol: str, quantity: float, trigger_price: float, last_price: float
    ) -> str:
        return f"mock-gtt-{symbol}-{int(trigger_price)}-{int(quantity)}"
