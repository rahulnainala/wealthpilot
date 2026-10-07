"""Integration tests for the per-fund endpoints."""

from __future__ import annotations

from httpx import AsyncClient


async def test_funds_list_orders_projection(client: AsyncClient) -> None:
    await client.post("/api/snapshots/refresh")
    await client.post(
        "/api/goals",
        json={
            "key": "travel",
            "name": "Travel Fund",
            "target_date": "2030-02-01",
            "target_value": 600000,
            "assigned_isins": ["INF179K01YM7"],
        },
    )

    funds = await client.get("/api/funds")
    assert funds.status_code == 200
    data = funds.json()
    assert len(data) == 6
    hdfc = next(f for f in data if f["isin"] == "INF179K01YM7")
    assert hdfc["recommendation"] == "keep_grow"
    assert hdfc["units"] > 0
    assert any(g["key"] == "travel" for g in hdfc["assigned_goals"])

    orders = await client.get("/api/funds/INF179K01YM7/orders")
    assert orders.status_code == 200
    rows = orders.json()
    assert len(rows) == 5  # five synthetic SIP installments
    assert all(r["transaction_type"] == "BUY" for r in rows)
    assert rows[0]["order_timestamp"] is not None

    projection = await client.get("/api/funds/INF179K01YM7/projection?years=5")
    assert projection.status_code == 200
    assert len(projection.json()) == 60


async def test_fund_projection_404_unknown(client: AsyncClient) -> None:
    await client.post("/api/snapshots/refresh")
    resp = await client.get("/api/funds/UNKNOWN/projection")
    assert resp.status_code == 404
