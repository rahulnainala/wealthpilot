"""Bucket classification and sleeve derivation for portfolio holdings.

Two axes, deliberately separate:

``Bucket`` — WHERE a holding sits / how the user files it. This is the value
persisted per holding and the one a user override writes to. Mutual funds always
land in ``MF``, because that is what they are: a wrapper.

``Sleeve`` — WHAT a holding actually contributes. Derived, never stored. A Nifty
50 index fund is simultaneously ``Bucket.MF`` (a fund) and ``Sleeve.GROWTH``
(equity growth exposure).

Why both exist: collapsing these onto one field is what made the growth rule
report ~8% growth for a portfolio holding ~44% equity growth. Everything held
through funds fell into ``MF`` and disappeared from the strategy axis — and
funds are how most growth exposure is actually held, so the rule was
structurally guaranteed to under-report. Allocation rules must read ``Sleeve``;
storage, user overrides and the MF audit read ``Bucket``.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from app.analytics.mf_audit import AssetClass, mf_asset_class
from app.analytics.models import HoldingView
from app.domain.enums import Bucket

# Dividend-oriented names: PSU energy, metals/miners, and REITs.
DIVIDEND_SYMBOLS: frozenset[str] = frozenset(
    {
        "BPCL",
        "COALINDIA",
        "IOC",
        "NMDC",
        "ONGC",
        "HINDZINC",
        "CASTROLIND",
        "POWERGRID",
        "GAIL",
        "HINDPETRO",
        # REITs
        "EMBASSY",
        "MINDSPACE",
        "BIRET",
        "BIRET-RR",
    }
)

# Gold and other holdings that sit outside the three-way growth/dividend/MF split.
OTHER_SYMBOLS: frozenset[str] = frozenset({"HDFCGOLD", "GOLDBEES"})


class Sleeve(StrEnum):
    """What a holding contributes, independent of the wrapper it arrives in."""

    GROWTH = "growth"
    DIVIDEND = "dividend"
    DEBT = "debt"
    GOLD = "gold"


def default_bucket_for_stock(symbol: str) -> Bucket:
    """Classify an equity/ETF symbol using the built-in default map."""
    normalized = symbol.strip().upper()
    if normalized in OTHER_SYMBOLS:
        return Bucket.OTHER
    if normalized in DIVIDEND_SYMBOLS:
        return Bucket.DIVIDEND
    return Bucket.GROWTH


def classify_stock(
    symbol: str, overrides: Mapping[str, Bucket] | None = None
) -> Bucket:
    """Classify an equity/ETF, honoring a per-symbol override if present."""
    if overrides:
        override = overrides.get(symbol.strip().upper())
        if override is not None:
            return override
    return default_bucket_for_stock(symbol)


def classify_mutual_fund() -> Bucket:
    """Mutual funds always occupy the ``MF`` bucket."""
    return Bucket.MF


def sleeve_for(bucket: Bucket, symbol: str) -> Sleeve:
    """Derive the strategy sleeve for a holding.

    Direct holdings map straight across. For a fund the bucket says nothing
    about what is inside, so we read the asset class already recorded in
    ``MF_AUDIT``: equity funds are growth exposure, debt funds are not.

    A fund with no audit metadata is treated as equity/growth — the same default
    ``audit_mf`` already applies, so an unrecognised ISIN cannot land in
    different sleeves depending on which module happens to ask.
    """
    if bucket is Bucket.OTHER:
        return Sleeve.GOLD
    if bucket is Bucket.DIVIDEND:
        return Sleeve.DIVIDEND
    if bucket is Bucket.GROWTH:
        return Sleeve.GROWTH

    asset_class = mf_asset_class(symbol)
    if asset_class is AssetClass.DEBT:
        return Sleeve.DEBT
    # EQUITY, HYBRID, or unknown. Hybrids are equity-majority in practice; if
    # that ever needs splitting, split it here, not at the call sites.
    return Sleeve.GROWTH


def sleeve_totals(holdings: list[HoldingView]) -> dict[Sleeve, float]:
    """Sum holding market values per sleeve (all sleeves present)."""
    totals: dict[Sleeve, float] = {s: 0.0 for s in Sleeve}
    for holding in holdings:
        sleeve = sleeve_for(holding.bucket, holding.symbol)
        totals[sleeve] = round(totals[sleeve] + holding.value, 2)
    return totals


def invested_value(holdings: list[HoldingView]) -> float:
    """Market value of everything held, excluding cash.

    Concentration is about how invested capital is distributed, so cash must not
    sit in the denominator — idle cash would otherwise make every position look
    better diversified than it is.
    """
    return round(sum(h.value for h in holdings), 2)


def non_gold_invested(holdings: list[HoldingView]) -> float:
    """Invested value excluding gold and cash — the base the three-way
    growth/dividend/MF split is measured against."""
    return round(
        sum(
            h.value
            for h in holdings
            if sleeve_for(h.bucket, h.symbol) is not Sleeve.GOLD
        ),
        2,
    )
