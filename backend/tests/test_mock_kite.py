"""Tests for MockKiteService seeded with the fictional fixture portfolio."""

from __future__ import annotations

from app.services.kite.mock import MockKiteService


async def test_holdings_shape_and_math() -> None:
    svc = MockKiteService()
    holdings = await svc.get_holdings()

    assert len(holdings) == 9
    ioc = next(h for h in holdings if h.tradingsymbol == "IOC")
    assert ioc.quantity == 30
    assert ioc.average_price == 151.20
    assert ioc.last_price == 146.10
    assert ioc.value == round(30 * 146.10, 2)
    assert ioc.invested == round(30 * 151.20, 2)
    assert ioc.pnl == round(ioc.value - ioc.invested, 2)


async def test_mf_holdings() -> None:
    svc = MockKiteService()
    mfs = await svc.get_mf_holdings()
    assert len(mfs) == 6
    isins = {m.isin for m in mfs}
    assert {"INF769K01DM9", "INF179K01YM7", "INF789F01XA0"} <= isins
    hdfc = next(m for m in mfs if m.isin == "INF179K01YM7")
    assert hdfc.quantity == 120.0
    assert "HDFC Short Term Debt" in hdfc.fund


async def test_margins_and_positions() -> None:
    svc = MockKiteService()
    margins = await svc.get_margins()
    assert margins.available_cash == 320.00
    assert await svc.get_positions() == []


async def test_index_quotes() -> None:
    svc = MockKiteService()
    quotes = await svc.get_index_quotes()
    names = {q.name for q in quotes}
    assert {"NIFTY 50", "NIFTY BANK"} <= names
    assert len(quotes) == 4


def test_auth_helpers() -> None:
    svc = MockKiteService()
    assert svc.get_login_url().startswith("https://kite.zerodha.com")
    token = svc.exchange_token("REQ99")
    assert token.access_token == "mock-access-REQ99"
    assert token.user_id == "MOCK123"
