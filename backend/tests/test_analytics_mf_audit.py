"""Tests for the MF audit."""

from __future__ import annotations

from app.analytics.mf_audit import Recommendation, audit_mf, mf_asset_class
from tests._fixtures import mock_holding_views


def _mf_views() -> list:
    from app.domain.enums import HoldingType

    return [h for h in mock_holding_views() if h.type == HoldingType.MF]


def test_audit_covers_all_six_funds() -> None:
    rows = audit_mf(_mf_views())
    assert len(rows) == 6
    by_isin = {r.isin: r for r in rows}

    # Mirae ELSS is the retire candidate.
    assert by_isin["INF769K01DM9"].recommendation == Recommendation.RETIRE.value
    # HDFC Short Term Debt is keep-and-grow (Emergency Fund vehicle).
    assert by_isin["INF179K01YM7"].recommendation == Recommendation.KEEP_GROW.value
    # UTI Nifty 50 carries an ETF alternative.
    assert by_isin["INF789F01XA0"].alternative_name == "NIFTYBEES"


def test_annual_cost_uses_er_override() -> None:
    rows = audit_mf(_mf_views(), er_overrides={"INF879O01027": 0.10})
    ppfc = next(r for r in rows if r.isin == "INF879O01027")
    assert ppfc.expense_ratio == 0.10
    assert ppfc.annual_cost == round(ppfc.value * 0.10 / 100, 2)


def test_asset_class_lookup() -> None:
    assert mf_asset_class("INF179K01YM7") is not None
    assert mf_asset_class("INF179K01YM7").value == "debt"
    assert mf_asset_class("INF789F01XA0").value == "equity"
    assert mf_asset_class("UNKNOWN") is None
