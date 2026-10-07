"""Real Kite Connect service wrapping the official ``pykiteconnect`` SDK.

The SDK is synchronous, so blocking calls are offloaded to a thread. Every
authenticated read is guarded against ``TokenException`` (daily token expiry),
which is re-raised as the domain-level :class:`KiteTokenExpired`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from kiteconnect import KiteConnect
from kiteconnect.exceptions import TokenException

from app.schemas.kite import (
    Holding,
    IndexQuote,
    KiteTokenResponse,
    Margins,
    MFHolding,
    MFOrder,
    Position,
)
from app.services.kite.base import BaseKiteService, KiteError, KiteTokenExpired
from app.services.kite.fixtures import CURATED_INDEX_SYMBOLS

T = TypeVar("T")


class KiteService(BaseKiteService):
    """Authenticated Kite Connect client for a single user session."""

    def __init__(
        self, api_key: str, api_secret: str, access_token: str | None = None
    ) -> None:
        self._api_secret = api_secret
        self._kite = KiteConnect(api_key=api_key)
        if access_token:
            self._kite.set_access_token(access_token)

    # --- Auth ----------------------------------------------------------------
    def get_login_url(self) -> str:
        url: str = self._kite.login_url()
        return url

    def exchange_token(self, request_token: str) -> KiteTokenResponse:
        try:
            data = self._kite.generate_session(
                request_token, api_secret=self._api_secret
            )
        except TokenException as exc:
            raise KiteTokenExpired(str(exc)) from exc
        except Exception as exc:  # network / API errors
            raise KiteError(f"Kite token exchange failed: {exc}") from exc
        return KiteTokenResponse(
            access_token=data["access_token"],
            user_id=data["user_id"],
            public_token=data.get("public_token"),
        )

    # --- Reads ---------------------------------------------------------------
    async def _call(self, fn: Callable[[], T]) -> T:
        """Run a blocking SDK call in a thread, mapping token errors."""

        def runner() -> T:
            try:
                return fn()
            except TokenException as exc:
                raise KiteTokenExpired(str(exc)) from exc
            except Exception as exc:
                raise KiteError(f"Kite API call failed: {exc}") from exc

        return await asyncio.to_thread(runner)

    async def get_holdings(self) -> list[Holding]:
        raw = await self._call(self._kite.holdings)
        return [
            Holding(
                tradingsymbol=h["tradingsymbol"],
                exchange=h.get("exchange", "NSE"),
                instrument_token=h.get("instrument_token", 0),
                isin=h.get("isin"),
                # Kite shows total holding = settled + T+1 (recent, unsettled) shares.
                quantity=h.get("quantity", 0) + h.get("t1_quantity", 0),
                average_price=h["average_price"],
                last_price=h["last_price"],
            )
            for h in raw
        ]

    async def get_mf_holdings(self) -> list[MFHolding]:
        raw = await self._call(self._kite.mf_holdings)
        return [
            MFHolding(
                isin=h.get("tradingsymbol") or h["fund"],
                fund=h["fund"],
                quantity=h["quantity"],
                average_price=h["average_price"],
                last_price=h["last_price"],
            )
            for h in raw
        ]

    async def get_mf_orders(self) -> list[MFOrder]:
        raw = await self._call(self._kite.mf_orders)
        return [
            MFOrder(
                order_id=str(o.get("order_id", "")),
                isin=o.get("tradingsymbol") or o.get("fund", ""),
                fund=o.get("fund", ""),
                transaction_type=o.get("transaction_type", "BUY"),
                status=o.get("status", ""),
                quantity=float(o.get("quantity", 0) or 0),
                amount=float(o.get("amount", 0) or 0),
                average_price=float(o.get("average_price", 0) or 0),
                order_timestamp=(
                    str(o["order_timestamp"]) if o.get("order_timestamp") else None
                ),
            )
            for o in raw
        ]

    async def get_positions(self) -> list[Position]:
        raw = await self._call(self._kite.positions)
        return [
            Position(
                tradingsymbol=p["tradingsymbol"],
                exchange=p.get("exchange", "NSE"),
                instrument_token=p.get("instrument_token", 0),
                product=p.get("product", "CNC"),
                quantity=p["quantity"],
                average_price=p["average_price"],
                last_price=p["last_price"],
            )
            for p in raw.get("net", [])
        ]

    async def get_margins(self) -> Margins:
        raw = await self._call(self._kite.margins)
        equity: dict[str, Any] = raw.get("equity", {}) if isinstance(raw, dict) else {}
        available = equity.get("available", {})
        return Margins(
            available_cash=float(available.get("cash", 0.0)),
            net=float(equity.get("net", 0.0)),
        )

    async def get_index_quotes(self) -> list[IndexQuote]:
        raw = await self._call(lambda: self._kite.quote(CURATED_INDEX_SYMBOLS))
        quotes: list[IndexQuote] = []
        for symbol, payload in raw.items():
            last_price = float(payload.get("last_price", 0.0))
            prev_close = float(payload.get("ohlc", {}).get("close", 0.0))
            change_pct = (
                round((last_price - prev_close) / prev_close * 100, 2)
                if prev_close
                else 0.0
            )
            quotes.append(
                IndexQuote(
                    name=symbol.split(":", 1)[-1],
                    instrument_token=payload.get("instrument_token", 0),
                    last_price=last_price,
                    change_pct=change_pct,
                )
            )
        return quotes

    async def place_gtt_sell(
        self, symbol: str, quantity: float, trigger_price: float, last_price: float
    ) -> str:
        """Place a real single-leg GTT SELL (CNC, LIMIT at the trigger). Phase 42."""
        k = self._kite

        def runner() -> object:
            return k.place_gtt(
                trigger_type=k.GTT_TYPE_SINGLE,
                tradingsymbol=symbol,
                exchange=k.EXCHANGE_NSE,
                trigger_values=[float(trigger_price)],
                last_price=float(last_price),
                orders=[
                    {
                        "transaction_type": k.TRANSACTION_TYPE_SELL,
                        "quantity": int(quantity),
                        "order_type": k.ORDER_TYPE_LIMIT,
                        "product": k.PRODUCT_CNC,
                        "price": float(trigger_price),
                    }
                ],
            )

        res = await self._call(runner)
        return str(res.get("trigger_id") if isinstance(res, dict) else res)
