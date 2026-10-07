"""Market-data provider layer (decoupled from Kite).

Holdings/P&L come from Zerodha (authoritative), but market context — index
quotes and live per-stock prices — can come from any provider. This keeps the
Market tab and the live ticker working on Zerodha's free Personal tier (or with
no Zerodha at all) by sourcing quotes elsewhere.
"""

from app.services.market.base import BaseMarketDataProvider, SymbolQuote
from app.services.market.factory import build_market_data_provider

__all__ = ["BaseMarketDataProvider", "SymbolQuote", "build_market_data_provider"]
