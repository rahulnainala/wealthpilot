"""WebSocket endpoint re-broadcasting live ticks to browser clients.

Ticker source, in priority order:
  1. A market-data provider (poll-based real prices) when MARKET_DATA_PROVIDER
     is set — works on Zerodha's free tier or with no Zerodha at all.
  2. Kite's WebSocket ticker when a live session exists (Connect tier).
  3. The mock random-walk ticker (default).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.db import get_sessionmaker
from app.domain.enums import HoldingType
from app.security.crypto import decrypt
from app.services.analytics_service import latest_holding_views
from app.services.kite import build_kite_service, fixtures
from app.services.kite_sessions import get_active_session
from app.services.market import build_market_data_provider
from app.services.ticker import tick_hub
from app.services.ticker.polling import PollingTickerService
from app.services.ticker.real import RealTickerService

router = APIRouter()


async def _held_stock_symbols() -> list[str]:
    """Stock symbols from the latest snapshot, or the fixture set as a fallback."""
    async with get_sessionmaker()() as db:
        data = await latest_holding_views(db)
    if data is not None:
        holdings, _cash = data
        symbols = [h.symbol for h in holdings if h.type == HoldingType.STOCK]
        if symbols:
            return symbols
    return [h.tradingsymbol for h in fixtures.mock_holdings()]


async def _configure_real_ticker(access_token: str) -> None:
    kite = build_kite_service(access_token)
    held = {
        h.instrument_token: h.tradingsymbol
        for h in await kite.get_holdings()
        if h.instrument_token
    }
    tokens = {**held, **fixtures.index_token_map()}
    settings = get_settings()
    tick_hub.set_ticker_factory(
        lambda: RealTickerService(settings.kite_api_key, access_token, tokens)
    )


async def _configure_ticker() -> None:
    """Choose the ticker source once, before the first client starts it."""
    if tick_hub.is_streaming:
        return
    settings = get_settings()

    # 1. Poll a market-data provider for real prices (any Zerodha tier).
    if settings.market_data_provider != "mock":
        symbols = await _held_stock_symbols()
        interval = settings.market_poll_seconds
        tick_hub.set_ticker_factory(
            lambda: PollingTickerService(
                build_market_data_provider(), symbols, interval
            )
        )
        return

    # 2. Kite WebSocket ticker when a live session exists.
    if not settings.use_mock_kite:
        async with get_sessionmaker()() as db:
            session = await get_active_session(db)
        if session is not None:
            await _configure_real_ticker(decrypt(session.access_token_encrypted))
    # 3. Otherwise the hub keeps its default mock ticker factory.


@router.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket) -> None:
    await _configure_ticker()

    await websocket.accept()
    await tick_hub.register(websocket)
    try:
        while True:
            # We don't expect client messages; this awaits until disconnect.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await tick_hub.unregister(websocket)
