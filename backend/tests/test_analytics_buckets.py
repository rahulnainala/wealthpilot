"""Tests for the pure bucket classifier."""

from __future__ import annotations

import pytest

from app.analytics.buckets import (
    classify_mutual_fund,
    classify_stock,
    default_bucket_for_stock,
)
from app.domain.enums import Bucket


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("BPCL", Bucket.DIVIDEND),
        ("ONGC", Bucket.DIVIDEND),
        ("COALINDIA", Bucket.DIVIDEND),
        ("EMBASSY", Bucket.DIVIDEND),  # REIT
        ("MINDSPACE", Bucket.DIVIDEND),  # REIT
        ("BIRET-RR", Bucket.DIVIDEND),  # REIT
        ("HDFCGOLD", Bucket.OTHER),  # gold sits outside the split
        ("GOLDBEES", Bucket.OTHER),
        ("INFY", Bucket.GROWTH),  # default for new direct buys
        ("TCS", Bucket.GROWTH),
    ],
)
def test_default_bucket_map(symbol: str, expected: Bucket) -> None:
    assert default_bucket_for_stock(symbol) == expected


def test_classification_is_case_insensitive() -> None:
    assert default_bucket_for_stock("bpcl") == Bucket.DIVIDEND
    assert default_bucket_for_stock("  ongc  ") == Bucket.DIVIDEND


def test_override_takes_precedence() -> None:
    overrides = {"ONGC": Bucket.GROWTH}
    assert classify_stock("ONGC", overrides) == Bucket.GROWTH
    # Non-overridden symbol still uses the default map.
    assert classify_stock("BPCL", overrides) == Bucket.DIVIDEND


def test_no_overrides_falls_back_to_default() -> None:
    assert classify_stock("HDFCGOLD") == Bucket.OTHER
    assert classify_stock("RANDOMCO", {}) == Bucket.GROWTH


def test_mutual_funds_always_mf_bucket() -> None:
    assert classify_mutual_fund() == Bucket.MF
