"""Tests for the market-data providers."""

from __future__ import annotations

import httpx

from app.services.market.indian_api import IndianApiMarketDataProvider
from app.services.market.mock import MockMarketDataProvider
from app.services.market.yahoo import YahooMarketDataProvider


async def test_mock_provider() -> None:
    provider = MockMarketDataProvider()
    assert len(await provider.get_index_quotes()) == 4
    quotes = await provider.get_quotes(["IOC", "ONGC"])
    assert {q.symbol for q in quotes} == {"IOC", "ONGC"}
    assert provider.index_is_fixture is True


async def test_mock_daily_returns_deterministic() -> None:
    provider = MockMarketDataProvider()
    first = await provider.get_daily_returns(["IOC", "ONGC"])
    assert set(first) == {"IOC", "ONGC"}
    assert len(first["IOC"]) == 60
    second = await provider.get_daily_returns(["IOC"])
    assert first["IOC"] == second["IOC"]  # deterministic per symbol


def _provider_with_handler(handler) -> IndianApiMarketDataProvider:
    provider = IndianApiMarketDataProvider("http://test")
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    )
    return provider


async def test_indian_api_parses_stock_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stock/list"
        assert request.url.params["symbols"] == "IOC,ONGC"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "count": 2,
                "stocks": [
                    {"symbol": "IOC", "last_price": 141.85, "percent_change": 1.74},
                    {"symbol": "ONGC", "last_price": 243.9, "percent_change": -4.18},
                ],
            },
        )

    provider = _provider_with_handler(handler)
    quotes = await provider.get_quotes(["IOC", "ONGC"])
    ioc = next(q for q in quotes if q.symbol == "IOC")
    assert ioc.last_price == 141.85
    assert ioc.change_pct == 1.74
    await provider.close()


async def test_indian_api_resilient_on_http_error() -> None:
    provider = _provider_with_handler(lambda request: httpx.Response(500))
    assert await provider.get_quotes(["IOC"]) == []
    await provider.close()


async def test_indian_api_indices_fall_back_to_fixtures() -> None:
    provider = IndianApiMarketDataProvider("http://test")
    assert len(await provider.get_index_quotes()) == 4
    assert provider.index_is_fixture is True
    await provider.close()


def _yahoo_with_handler(handler) -> YahooMarketDataProvider:
    provider = YahooMarketDataProvider()
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://query1.finance.yahoo.com",
    )
    return provider


async def test_yahoo_parses_real_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        symbol = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": symbol,
                                "regularMarketPrice": 100.0,
                                "chartPreviousClose": 98.0,
                            }
                        }
                    ]
                }
            },
        )

    provider = _yahoo_with_handler(handler)
    quotes = await provider.get_quotes(["IOC"])
    assert quotes[0].symbol == "IOC"
    assert quotes[0].last_price == 100.0
    assert quotes[0].change_pct == round((100 - 98) / 98 * 100, 2)

    indices = await provider.get_index_quotes()
    assert len(indices) == 4
    assert provider.index_is_fixture is False  # real index feed
    await provider.close()


async def test_yahoo_skips_failed_symbols() -> None:
    provider = _yahoo_with_handler(lambda request: httpx.Response(404))
    assert await provider.get_quotes(["IOC", "ONGC"]) == []
    assert await provider.get_index_quotes() == []
    await provider.close()
