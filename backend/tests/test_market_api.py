"""Integration test for the market overview endpoint."""

from __future__ import annotations

from httpx import AsyncClient


async def test_market_overview(client: AsyncClient) -> None:
    resp = await client.get("/api/market/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_fixture"] is True  # mock mode in tests
    names = {i["name"] for i in body["indices"]}
    assert {"NIFTY 50", "NIFTY BANK"} <= names
    assert len(body["indices"]) == 4
    for item in body["indices"]:
        assert "last_price" in item and "change_pct" in item
