"""Tests for the issue-detection rules."""

from __future__ import annotations

from app.analytics.issues import detect_issues
from app.analytics.models import HoldingView, Severity
from app.domain.enums import Bucket, HoldingType
from tests._fixtures import MOCK_CASH, mock_holding_views


def _codes(issues: list) -> set[str]:
    return {i.code for i in issues}


def test_fixture_portfolio_triggers_expected_issues() -> None:
    issues = detect_issues(mock_holding_views(), MOCK_CASH)
    codes = _codes(issues)

    # Critical: dividend is ~46% of the non-gold split, over the 45% ceiling.
    assert "dividend_overweight" in codes
    # Growth must NOT fire: the equity index funds ARE the growth sleeve, and
    # they put growth well above — above the 33% target. This used to
    # fire because funds were counted as `MF` and vanished from the growth axis.
    assert "growth_missing_third" not in codes
    # Warnings.
    assert "psu_energy_cluster" in codes
    assert "single_symbol_concentration" in codes
    assert "position_too_small" in codes
    assert "duplicate_elss" in codes
    # Info.
    assert "low_cash" in codes  # cash ₹320
    assert "gold_overweight" in codes
    # Gold raises ONE issue, not two: `gold_overweight` and
    # `single_symbol_concentration` share the same 8% threshold.
    assert not any(
        i.code == "single_symbol_concentration" and i.symbols == ["HDFCGOLD"]
        for i in issues
    )

    # Sorted most-severe first.
    rank = {"critical": 0, "warning": 1, "info": 2}
    severities = [i.severity for i in issues]
    assert severities == sorted(severities, key=lambda s: rank[s])
    assert issues[0].severity == Severity.CRITICAL


def test_empty_portfolio_has_no_issues() -> None:
    assert detect_issues([], 0.0) == []


def _hv(symbol: str, bucket: Bucket, value: float, pnl_pct: float = 0.0) -> HoldingView:
    invested = value / (1 + pnl_pct / 100) if pnl_pct != -100 else 0.0
    return HoldingView(
        symbol=symbol,
        bucket=bucket,
        type=HoldingType.STOCK,
        value=value,
        invested=round(invested, 2),
        pnl=round(value - invested, 2),
        pnl_pct=pnl_pct,
    )


def test_balanced_portfolio_no_concentration_issues() -> None:
    # Growth ~34%, dividend ~33%, gold ~0; all positions moderate.
    holdings = [
        _hv("INFY", Bucket.GROWTH, 34_000),
        _hv("HDFCBANK", Bucket.GROWTH, 33_000),
        _hv("ITC", Bucket.DIVIDEND, 33_000),
    ]
    codes = _codes(detect_issues(holdings, cash=5_000))
    assert "growth_missing_third" not in codes
    assert "dividend_overweight" not in codes
    assert "low_cash" not in codes


def test_drawdown_and_single_symbol_rules() -> None:
    holdings = [
        _hv("BIGCO", Bucket.GROWTH, 50_000, pnl_pct=-12.0),  # >8% and drawdown
        _hv("SMALLCO", Bucket.GROWTH, 40_000),
    ]
    issues = detect_issues(holdings, cash=10_000)
    codes = _codes(issues)
    assert "single_symbol_concentration" in codes
    assert "position_drawdown" in codes
    drawdown = next(i for i in issues if i.code == "position_drawdown")
    assert drawdown.amount is not None and drawdown.amount < 0
    # A drawdown is the market moving, not a construction defect — it must not
    # outrank real allocation problems in the list.
    assert drawdown.severity == Severity.INFO


# ─── Regression tests for the 2026-08 issue-engine fixes ────────────────────


def _mf(isin: str, value: float) -> HoldingView:
    return HoldingView(
        symbol=isin,
        bucket=Bucket.MF,
        type=HoldingType.MF,
        value=value,
        invested=value,
        pnl=0.0,
        pnl_pct=0.0,
    )


def test_equity_fund_counts_toward_growth() -> None:
    """The core bug: growth held through funds was invisible to the growth rule.

    UTI Nifty 50 Index is equity. A portfolio that is 100% Nifty index fund has
    100% growth exposure and must not be told its growth third is missing.
    """
    codes = _codes(detect_issues([_mf("INF789F01XA0", 50_000)], cash=1_000))
    assert "growth_missing_third" not in codes


def test_debt_fund_does_not_count_toward_growth() -> None:
    """HDFC Short Term Debt is DEBT — real growth exposure here is zero."""
    codes = _codes(detect_issues([_mf("INF179K01YM7", 50_000)], cash=1_000))
    assert "growth_missing_third" in codes


def test_growth_measured_against_non_gold_base() -> None:
    """Gold sits outside the three-way split, so it must not dilute growth.

    ₹30k growth + ₹30k gold is 50% of everything but 100% of the non-gold
    split — a full third and then some. Against `total` it read as 50%, and
    against the message's own 33%-of-non-gold target that was incomparable.
    """
    holdings = [_hv("INFY", Bucket.GROWTH, 30_000), _hv("HDFCGOLD", Bucket.OTHER, 30_000)]
    assert "growth_missing_third" not in _codes(detect_issues(holdings, cash=0.0))


def test_tiny_position_rule_suppressed_on_small_portfolios() -> None:
    """Below ₹18,750 invested, the ₹1,500 floor exceeds the 8% cap, so every
    holding would trip one rule or the other. The advice is noise — suppress it."""
    holdings = [_hv("A", Bucket.GROWTH, 1_000), _hv("B", Bucket.GROWTH, 1_200)]
    assert "position_too_small" not in _codes(detect_issues(holdings, cash=0.0))


def test_tiny_position_rule_applies_once_portfolio_is_large_enough() -> None:
    holdings = [_hv("BIG", Bucket.GROWTH, 60_000), _hv("DUST", Bucket.GROWTH, 900)]
    assert "position_too_small" in _codes(detect_issues(holdings, cash=0.0))


def test_cash_does_not_dilute_concentration() -> None:
    """One ₹10k holding beside ₹90k cash is 100% of INVESTED capital, however
    small it looks against total portfolio value."""
    holdings = [_hv("ONLYCO", Bucket.GROWTH, 10_000)]
    issues = detect_issues(holdings, cash=90_000)
    conc = next(i for i in issues if i.code == "single_symbol_concentration")
    assert conc.pct_of_total == 100.0
