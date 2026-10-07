"""Select the configured market-data provider."""

from __future__ import annotations

from app.config import get_settings
from app.services.market.base import BaseMarketDataProvider
from app.services.market.mock import MockMarketDataProvider


def build_market_data_provider() -> BaseMarketDataProvider:
    """Return a provider per ``MARKET_DATA_PROVIDER`` (default mock).

    Providers are imported lazily so the mock path needs no httpx setup.
    """
    settings = get_settings()
    provider = settings.market_data_provider

    if provider == "yahoo":
        from app.services.market.yahoo import YahooMarketDataProvider

        return YahooMarketDataProvider(settings.market_data_timeout_seconds)
    if provider == "indianapi":
        from app.services.market.indian_api import IndianApiMarketDataProvider

        return IndianApiMarketDataProvider(
            settings.market_data_base_url, settings.market_data_timeout_seconds
        )
    return MockMarketDataProvider()
