"""Integration tests for the target-allocation basket (SIP-routing model)."""

from __future__ import annotations

from httpx import AsyncClient


async def _seed_goals(client: AsyncClient) -> None:
    await client.post("/api/goals", json={
        "key": "travel", "name": "Travel Fund", "monthly_contribution": 10000,
        "assigned_isins": ["INF789F01XA0", "INF879O01027"]})
    await client.post("/api/goals", json={
        "key": "vehicle", "name": "Vehicle Fund", "monthly_contribution": 6000,
        "assigned_isins": ["INF204KB18Z7"]})
    # The Emergency Fund absorbs FI's paused share: a real monthly SIP, not
    # bonus-only.
    await client.post("/api/goals", json={
        "key": "emergency", "name": "Emergency Fund", "monthly_contribution": 4000,
        "assigned_isins": ["INF179K01YM7"]})
    # FI is paused until 2030 — no new SIP, held positions only.
    await client.post("/api/goals", json={
        "key": "fi", "name": "Financial Independence", "monthly_contribution": 0,
        "assigned_isins": ["INF0R8F01026", "INF769K01DM9", "HDFCGOLD"]})


async def test_basket_routing_hold_and_legacy(client: AsyncClient) -> None:
    await client.post("/api/snapshots/refresh")
    await _seed_goals(client)

    basket = (await client.get("/api/basket")).json()
    assert basket["total_value"] > 0
    sleeves = {s["goal_key"]: s for s in basket["sleeves"]}

    travel = sleeves["travel"]
    assert all(p["mode"] == "core" for p in travel["positions"])
    assert round(sum(p["sip_pct"] for p in travel["positions"])) == 100

    # FI is paused: only held positions, no new-money row.
    fi = sleeves["fi"]
    holds = [p for p in fi["positions"] if p["mode"] == "hold"]
    assert len(holds) >= 3  # 2 ELSS + gold, held with no new money
    assert all(p["sip_monthly"] == 0 for p in holds)
    assert not any(p["mode"] == "planned" for p in fi["positions"])

    # The Emergency Fund carries a real SIP (core mode), absorbed from FI.
    emergency = sleeves["emergency"]
    assert emergency["positions"][0]["mode"] == "core"
    assert emergency["positions"][0]["sip_monthly"] == 4000

    # Legacy REIT/PSU positions are unassigned.
    assert len(basket["legacy"]) > 0
    assert all("reposition" in h["note"].lower() for h in basket["legacy"])

    assert abs(sum(s["pct"] for s in basket["monthly_split"]) - 100.0) < 1.0
