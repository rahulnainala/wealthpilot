"""Liabilities + honest net worth.

The bug these pin: /api/assets/networth returned ``portfolio + external`` under
the name "net worth". That is gross assets. Against a loan many times the size
of the portfolio it did not merely round badly — it reported a healthily positive net
worth for a position that is deeply negative, and the error grew with the debt.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
async def with_snapshot(client: AsyncClient) -> AsyncClient:
    resp = await client.post("/api/snapshots/refresh")
    assert resp.status_code == 200
    return client


GOLD_LOAN = {
    "name": "Gold loan",
    "kind": "gold_loan",
    "principal": 500_000.0,
    "outstanding": 500_000.0,
    "rate_pct": None,
    "emi": None,
    "start_date": None,
    "term_months": 36,
}


async def test_net_worth_subtracts_liabilities(with_snapshot: AsyncClient) -> None:
    before = (await with_snapshot.get("/api/assets/networth")).json()
    assert before["liabilities"] == 0
    assert before["net_worth"] == before["assets"]

    resp = await with_snapshot.post("/api/assets/liabilities", json=GOLD_LOAN)
    assert resp.status_code == 201

    after = (await with_snapshot.get("/api/assets/networth")).json()
    assert after["liabilities"] == 500_000.0
    # Assets are unchanged; only the net figure moves.
    assert after["assets"] == before["assets"]
    assert after["net_worth"] == pytest.approx(after["assets"] - 500_000.0)


async def test_net_worth_goes_negative_when_debt_exceeds_assets(
    with_snapshot: AsyncClient,
) -> None:
    """The case the old endpoint could not express at all.

    A loan many times the size of the book, and 'net worth' must be
    allowed to be a large negative number rather than silently
    reporting the asset side alone.
    """
    await with_snapshot.post("/api/assets/liabilities", json=GOLD_LOAN)
    body = (await with_snapshot.get("/api/assets/networth")).json()
    assert body["net_worth"] < 0
    assert body["assets"] > 0  # assets are still reported, just not as "net"


async def test_liabilities_round_trip(with_snapshot: AsyncClient) -> None:
    created = (
        await with_snapshot.post("/api/assets/liabilities", json=GOLD_LOAN)
    ).json()
    assert created["kind"] == "gold_loan"
    assert created["term_months"] == 36

    listed = (await with_snapshot.get("/api/assets/liabilities")).json()
    assert [row["name"] for row in listed] == ["Gold loan"]

    resp = await with_snapshot.delete(f"/api/assets/liabilities/{created['id']}")
    assert resp.status_code == 204
    assert (await with_snapshot.get("/api/assets/liabilities")).json() == []

    body = (await with_snapshot.get("/api/assets/networth")).json()
    assert body["liabilities"] == 0


async def test_deleting_a_missing_liability_404s(with_snapshot: AsyncClient) -> None:
    assert (await with_snapshot.delete("/api/assets/liabilities/9999")).status_code == 404


async def test_optional_fields_may_be_omitted(with_snapshot: AsyncClient) -> None:
    """A gold loan is often bullet/interest-only — no EMI, and the rate may not
    be to hand when the row is first entered. Requiring them would push the
    owner to invent numbers, which is worse than recording none."""
    minimal = {
        "name": "Gold loan",
        "kind": "gold_loan",
        "principal": 500_000.0,
        "outstanding": 475_000.0,
    }
    resp = await with_snapshot.post("/api/assets/liabilities", json=minimal)
    assert resp.status_code == 201
    body = resp.json()
    assert body["emi"] is None and body["rate_pct"] is None
