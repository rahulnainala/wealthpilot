"""Mutual-fund audit: static metadata keyed by ISIN, rendered with live values.

Expense ratios are approximate and editable via the settings store; pass an
``er_overrides`` map to substitute user-tuned values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.analytics.models import HoldingView


class AssetClass(StrEnum):
    EQUITY = "equity"
    DEBT = "debt"
    HYBRID = "hybrid"


class Recommendation(StrEnum):
    KEEP = "keep"
    KEEP_GROW = "keep_grow"
    RETIRE = "retire"


@dataclass(frozen=True)
class MFMeta:
    isin: str
    name: str
    category: str
    asset_class: AssetClass
    expense_ratio: float  # approximate %, editable in settings
    recommendation: Recommendation
    rationale: str
    goal_tag: str | None = None
    alternative_name: str | None = None
    alternative_er: float | None = None


MF_AUDIT: dict[str, MFMeta] = {
    "INF789F01XA0": MFMeta(
        isin="INF789F01XA0",
        name="UTI Nifty 50 Index",
        category="Large-cap index (Nifty 50)",
        asset_class=AssetClass.EQUITY,
        expense_ratio=0.19,
        recommendation=Recommendation.KEEP,
        rationale="Core index vehicle. Cheaper ETF exists but SIP autopilot wins.",
        goal_tag="Travel Fund",
        alternative_name="NIFTYBEES",
        alternative_er=0.04,
    ),
    "INF879O01027": MFMeta(
        isin="INF879O01027",
        name="Parag Parikh Flexi Cap",
        category="Flexi cap",
        asset_class=AssetClass.EQUITY,
        expense_ratio=0.63,
        recommendation=Recommendation.KEEP,
        rationale="Long-term core — global sleeve + cash buffer not replicable by index.",
        goal_tag="Travel Fund",
    ),
    "INF204KB18Z7": MFMeta(
        isin="INF204KB18Z7",
        name="Nippon Nifty Midcap 150 Index",
        category="Mid-cap index",
        asset_class=AssetClass.EQUITY,
        expense_ratio=0.30,
        recommendation=Recommendation.KEEP,
        rationale="Mid-cap index sleeve for long-term growth.",
        goal_tag="Vehicle Fund",
        alternative_name="MID150BEES",
        alternative_er=0.21,
    ),
    "INF0R8F01158": MFMeta(
        isin="INF0R8F01158",
        name="Zerodha Nifty 50 Index",
        category="Large-cap index (Nifty 50)",
        asset_class=AssetClass.EQUITY,
        expense_ratio=0.20,
        recommendation=Recommendation.KEEP,
        rationale="Large-cap sleeve balancing the Vehicle Fund's midcap half.",
        goal_tag="Vehicle Fund",
    ),
    "INF0R8F01026": MFMeta(
        isin="INF0R8F01026",
        name="Zerodha ELSS LargeMidcap 250",
        category="ELSS index (LargeMidcap 250)",
        asset_class=AssetClass.EQUITY,
        expense_ratio=0.27,
        recommendation=Recommendation.KEEP,
        rationale="Low-cost 80C vehicle with long-term index exposure.",
        goal_tag="80C + long-term (FI — paused)",
    ),
    "INF769K01DM9": MFMeta(
        isin="INF769K01DM9",
        name="Mirae Asset ELSS Tax Saver",
        category="ELSS (active)",
        asset_class=AssetClass.EQUITY,
        expense_ratio=0.59,
        recommendation=Recommendation.RETIRE,
        rationale="Duplicate 80C vehicle — redeem as 3-year locks expire, redirect to Growth.",
        goal_tag="80C (duplicate) (FI — paused)",
    ),
    "INF179K01YM7": MFMeta(
        isin="INF179K01YM7",
        name="HDFC Short Term Debt",
        category="Short-duration debt",
        asset_class=AssetClass.DEBT,
        expense_ratio=0.29,
        recommendation=Recommendation.KEEP_GROW,
        rationale=(
            "Short-duration debt — the Emergency Fund vehicle (SIP + bonus-funded). "
            "Keep and grow."
        ),
        goal_tag="Emergency Fund",
    ),
}


@dataclass(frozen=True)
class MFAuditRow:
    isin: str
    name: str
    category: str
    asset_class: str
    expense_ratio: float
    recommendation: str
    rationale: str
    goal_tag: str | None
    alternative_name: str | None
    alternative_er: float | None
    value: float
    pnl: float
    annual_cost: float  # value * effective ER


def mf_asset_class(isin: str) -> AssetClass | None:
    meta = MF_AUDIT.get(isin)
    return meta.asset_class if meta else None


def audit_mf(
    mf_holdings: list[HoldingView], er_overrides: dict[str, float] | None = None
) -> list[MFAuditRow]:
    """Join MF metadata with live holding values, applying ER overrides."""
    overrides = er_overrides or {}
    rows: list[MFAuditRow] = []
    for holding in mf_holdings:
        meta = MF_AUDIT.get(holding.symbol)
        expense_ratio = overrides.get(
            holding.symbol, meta.expense_ratio if meta else 0.0
        )
        rows.append(
            MFAuditRow(
                isin=holding.symbol,
                name=meta.name if meta else (holding.name or holding.symbol),
                category=meta.category if meta else "Unknown",
                asset_class=(meta.asset_class.value if meta else AssetClass.EQUITY.value),
                expense_ratio=expense_ratio,
                recommendation=(
                    meta.recommendation.value if meta else Recommendation.KEEP.value
                ),
                rationale=meta.rationale if meta else "No audit metadata on file.",
                goal_tag=meta.goal_tag if meta else None,
                alternative_name=meta.alternative_name if meta else None,
                alternative_er=meta.alternative_er if meta else None,
                value=holding.value,
                pnl=holding.pnl,
                annual_cost=round(holding.value * expense_ratio / 100, 2),
            )
        )
    return rows
