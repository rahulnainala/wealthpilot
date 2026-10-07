"""Abstract Kite service interface and domain exceptions.

Both the real (:class:`~app.services.kite.real.KiteService`) and mock
(:class:`~app.services.kite.mock.MockKiteService`) implementations conform to
this interface, so the rest of the app is agnostic to which one is wired in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.kite import (
    Holding,
    IndexQuote,
    KiteTokenResponse,
    Margins,
    MFHolding,
    MFOrder,
    Position,
)


class KiteError(Exception):
    """Base class for Kite-related failures."""


class KiteNotConnected(KiteError):
    """No active (non-stale) Kite session is available."""


class KiteTokenExpired(KiteError):
    """The Kite access token has expired (SDK ``TokenException``).

    Kite tokens expire daily at ~6 AM IST. Callers should surface a
    "Reconnect Zerodha" prompt rather than a generic error.
    """


class BaseKiteService(ABC):
    """Interface for reading portfolio data from Zerodha Kite Connect."""

    # --- Auth (synchronous, cheap) -------------------------------------------
    @abstractmethod
    def get_login_url(self) -> str:
        """Return the Kite Connect login URL to redirect the user to."""

    @abstractmethod
    def exchange_token(self, request_token: str) -> KiteTokenResponse:
        """Exchange a ``request_token`` for an access token (uses API secret)."""

    # --- Reads (async; may hit the network) ----------------------------------
    @abstractmethod
    async def get_holdings(self) -> list[Holding]:
        """Return direct equity/ETF holdings."""

    @abstractmethod
    async def get_mf_holdings(self) -> list[MFHolding]:
        """Return mutual fund holdings."""

    @abstractmethod
    async def get_mf_orders(self) -> list[MFOrder]:
        """Return mutual fund order history (purchases/redemptions)."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return net intraday/derivative positions."""

    @abstractmethod
    async def get_margins(self) -> Margins:
        """Return account margins / available cash."""

    @abstractmethod
    async def get_index_quotes(self) -> list[IndexQuote]:
        """Return quotes for the curated index/sector list."""

    async def place_gtt_sell(
        self, symbol: str, quantity: float, trigger_price: float, last_price: float
    ) -> str:
        """Place a single-leg GTT SELL and return its id. WRITE op (Phase 42).

        Not supported by default; real/mock services override it. Callers must
        gate this behind auth + explicit confirmation + audit logging.
        """
        raise KiteError("Order placement is not supported by this service.")
