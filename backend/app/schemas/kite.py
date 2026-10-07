"""Domain DTOs for Kite Connect data.

These normalize the raw pykiteconnect dict responses into typed models with a
handful of derived money figures (value, invested, P&L) that the analytics
engine and snapshot layer consume. Keeping the derivations here means both the
real and mock services return identical, ready-to-use shapes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, computed_field


class _Instrument(BaseModel):
    """Shared money math for a quantity held at an average and last price."""

    model_config = ConfigDict(frozen=True)

    quantity: float
    average_price: float
    last_price: float

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value(self) -> float:
        """Current market value of the position."""
        return round(self.quantity * self.last_price, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def invested(self) -> float:
        """Cost basis of the position."""
        return round(self.quantity * self.average_price, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pnl(self) -> float:
        """Absolute unrealized profit/loss in rupees."""
        return round(self.value - self.invested, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pnl_pct(self) -> float:
        """Unrealized P&L as a percentage of cost basis."""
        if self.invested == 0:
            return 0.0
        return round((self.pnl / self.invested) * 100, 2)


class Holding(_Instrument):
    """A direct equity/ETF holding (Kite ``holdings()``)."""

    tradingsymbol: str
    exchange: str = "NSE"
    instrument_token: int = 0
    isin: str | None = None


class MFHolding(_Instrument):
    """A mutual fund holding (Kite ``mf_holdings()``), keyed by ISIN."""

    isin: str
    fund: str
    # ``quantity`` = units, ``average_price``/``last_price`` = avg NAV / NAV.


class Position(_Instrument):
    """An intraday/derivatives position (Kite ``positions()['net']``)."""

    tradingsymbol: str
    exchange: str = "NSE"
    instrument_token: int = 0
    product: str = "CNC"


class Margins(BaseModel):
    """Account margins / available cash (Kite ``margins()``)."""

    model_config = ConfigDict(frozen=True)

    available_cash: float = 0.0
    net: float = 0.0


class IndexQuote(BaseModel):
    """A curated index/sector quote (Kite ``quote()`` for index tokens)."""

    model_config = ConfigDict(frozen=True)

    name: str
    instrument_token: int = 0
    last_price: float
    change_pct: float


class KiteTokenResponse(BaseModel):
    """Result of exchanging a Kite ``request_token`` for an access token."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    user_id: str
    public_token: str | None = None


class MFOrder(BaseModel):
    """A mutual-fund order (Kite ``mf_orders()``) — a purchase/redemption event."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    isin: str
    fund: str
    transaction_type: str = "BUY"  # BUY | SELL
    status: str = ""
    quantity: float = 0.0  # units
    amount: float = 0.0
    average_price: float = 0.0  # NAV
    order_timestamp: str | None = None
