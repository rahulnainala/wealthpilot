"""Seed portfolio fixture data — a fictional investor, not a real account.

Used both as the :class:`~app.services.kite.mock.MockKiteService` seed and as the
canonical test fixtures. The mix is chosen so every analytics rule has
something to find: a PSU-energy cluster, a concentrated name, a position too
small to matter, a drawdown, a REIT, gold and a set of index funds. Instrument
tokens are arbitrary but stable placeholders — the real service resolves live
tokens from Kite's instrument dump (Phase 5B). Prices and index quotes are
plausible placeholder values, NOT real market quotes.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.schemas.kite import Holding, IndexQuote, MFHolding, MFOrder

# --- Direct equity / ETF holdings --------------------------------------------
# (tradingsymbol, instrument_token, quantity, average_price, last_price)
_STOCKS: list[tuple[str, int, float, float, float]] = [
    ("COALINDIA", 900001, 18, 402.10, 431.50),
    ("ONGC", 900002, 26, 262.40, 248.75),
    ("IOC", 900003, 30, 151.20, 146.10),
    ("POWERGRID", 900004, 15, 298.50, 312.40),
    ("EMBASSY", 900005, 6, 372.80, 401.20),
    ("HDFCGOLD", 900006, 50, 118.40, 123.60),
    ("ITC", 900007, 2, 455.00, 401.30),
    ("INFY", 900008, 4, 1_520.00, 1_490.00),
    ("NMDC", 900009, 40, 72.10, 70.80),
]

# --- Mutual fund holdings (keyed by ISIN) ------------------------------------
# (isin, fund, units, average_nav, nav)
_MFS: list[tuple[str, str, float, float, float]] = [
    (
        "INF769K01DM9",
        "Mirae Asset ELSS Tax Saver Fund - Direct Growth",
        18.4,
        52.10,
        57.36,
    ),
    (
        "INF0R8F01026",
        "Zerodha ELSS Tax Saver Nifty LargeMidcap 250 Index Fund - Direct Growth",
        150.0,
        11.20,
        14.30,
    ),
    (
        "INF789F01XA0",
        "UTI Nifty 50 Index Fund - Direct Growth",
        62.5,
        158.40,
        168.59,
    ),
    (
        "INF879O01027",
        "Parag Parikh Flexi Cap Fund - Direct Growth",
        35.2,
        84.70,
        90.30,
    ),
    (
        "INF179K01YM7",
        "HDFC Short Term Debt Fund - Direct Growth",
        120.0,
        33.10,
        35.22,
    ),
    (
        "INF204KB18Z7",
        "Nippon India Nifty Midcap 150 Index Fund - Direct Growth",
        210.0,
        24.10,
        26.40,
    ),
]

# --- Curated index / sector list (Phase 5B) ----------------------------------
# (name, instrument_token, kite_quote_symbol, last_price, change_pct)
# ``kite_quote_symbol`` is what the real service passes to ``kite.quote()``.
_INDICES: list[tuple[str, int, str, float, float]] = [
    ("NIFTY 50", 256265, "NSE:NIFTY 50", 24_850.0, 0.4),
    ("NIFTY BANK", 260105, "NSE:NIFTY BANK", 53_200.0, 0.2),
    ("Energy/PSU proxy", 289545, "NSE:NIFTY ENERGY", 11_400.0, -0.3),
    ("Metal proxy", 267273, "NSE:NIFTY METAL", 9_700.0, 0.6),
]

# Symbols the real KiteService quotes for the market-overview endpoint.
CURATED_INDEX_SYMBOLS: list[str] = [row[2] for row in _INDICES]

# Cash balance (₹).
MOCK_CASH: float = 320.00


def mock_holdings() -> list[Holding]:
    return [
        Holding(
            tradingsymbol=sym,
            instrument_token=token,
            quantity=qty,
            average_price=avg,
            last_price=ltp,
        )
        for sym, token, qty, avg, ltp in _STOCKS
    ]


def mock_mf_holdings() -> list[MFHolding]:
    return [
        MFHolding(
            isin=isin,
            fund=fund,
            quantity=units,
            average_price=avg_nav,
            last_price=nav,
        )
        for isin, fund, units, avg_nav, nav in _MFS
    ]


def mock_mf_orders() -> list[MFOrder]:
    """Synthetic SIP-like order history for each fund (BUY, monthly)."""
    orders: list[MFOrder] = []
    order_id = 1000
    for isin, fund, units, avg_nav, _nav in _MFS:
        installments = 5
        per_units = round(units / installments, 3)
        for i in range(installments):
            when = date(2025, 8, 1) + timedelta(days=30 * i)
            order_nav = round(avg_nav * (0.95 + 0.025 * i), 2)
            orders.append(
                MFOrder(
                    order_id=str(order_id),
                    isin=isin,
                    fund=fund,
                    transaction_type="BUY",
                    status="COMPLETE",
                    quantity=per_units,
                    amount=round(per_units * order_nav, 2),
                    average_price=order_nav,
                    order_timestamp=f"{when.isoformat()}T10:00:00",
                )
            )
            order_id += 1
    return orders


def mock_index_quotes() -> list[IndexQuote]:
    return [
        IndexQuote(
            name=name,
            instrument_token=token,
            last_price=last_price,
            change_pct=change_pct,
        )
        for name, token, _symbol, last_price, change_pct in _INDICES
    ]


def ticker_seed() -> dict[int, tuple[str, float]]:
    """Map instrument_token -> (display symbol, base price) for the mock ticker."""
    seed: dict[int, tuple[str, float]] = {}
    for sym, token, _qty, _avg, ltp in _STOCKS:
        seed[token] = (sym, ltp)
    for name, token, _symbol, last_price, _change in _INDICES:
        seed[token] = (name, last_price)
    return seed


def index_token_map() -> dict[int, str]:
    """Map instrument_token -> name for the curated indices only."""
    return {token: name for name, token, *_ in _INDICES}


def instrument_token_map() -> dict[int, str]:
    """Map instrument_token -> display symbol for all streamable instruments.

    Consumed by the mock ticker (Phase 5) to emit random-walk ticks.
    """
    tokens: dict[int, str] = {}
    for sym, token, *_ in _STOCKS:
        tokens[token] = sym
    for name, token, *_ in _INDICES:
        tokens[token] = name
    return tokens
