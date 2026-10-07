"""Integration tests for goals / contributions / overrides / settings CRUD."""

from __future__ import annotations

from httpx import AsyncClient


# --- Goals -------------------------------------------------------------------
async def test_goals_crud(client: AsyncClient) -> None:
    created = await client.post(
        "/api/goals",
        json={"key": "car", "name": "New Car", "target_value": 800000},
    )
    assert created.status_code == 201
    goal_id = created.json()["id"]

    # Duplicate key rejected.
    dup = await client.post("/api/goals", json={"key": "car", "name": "Dup"})
    assert dup.status_code == 409

    listed = await client.get("/api/goals")
    assert any(g["key"] == "car" for g in listed.json())

    updated = await client.put(
        f"/api/goals/{goal_id}", json={"monthly_contribution": 5000}
    )
    assert updated.status_code == 200
    assert updated.json()["monthly_contribution"] == 5000
    assert updated.json()["name"] == "New Car"  # unchanged fields preserved

    deleted = await client.delete(f"/api/goals/{goal_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/goals/{goal_id}")).status_code == 404


# --- Contributions -----------------------------------------------------------
async def test_contributions_upsert_and_month_normalization(
    client: AsyncClient,
) -> None:
    first = await client.post(
        "/api/contributions",
        json={"bucket": "growth", "month": "2027-03-15", "amount": 10000},
    )
    assert first.status_code == 201
    assert first.json()["month"] == "2027-03-01"  # normalized to first of month

    # Same bucket+month updates rather than duplicating.
    second = await client.post(
        "/api/contributions",
        json={"bucket": "growth", "month": "2027-03-28", "amount": 12000},
    )
    assert second.json()["amount"] == 12000
    assert second.json()["id"] == first.json()["id"]

    listed = await client.get("/api/contributions")
    assert len(listed.json()) == 1


# --- Bucket overrides --------------------------------------------------------
async def test_bucket_overrides(client: AsyncClient) -> None:
    created = await client.post(
        "/api/bucket-overrides", json={"symbol": "infy", "bucket": "dividend"}
    )
    assert created.status_code == 201
    assert created.json()["symbol"] == "INFY"  # normalized upper-case

    # Invalid bucket value rejected by enum validation.
    bad = await client.post(
        "/api/bucket-overrides", json={"symbol": "TCS", "bucket": "banana"}
    )
    assert bad.status_code == 422

    override_id = created.json()["id"]
    assert (await client.delete(f"/api/bucket-overrides/{override_id}")).status_code == 204


# --- Settings ----------------------------------------------------------------
async def test_settings_put_get(client: AsyncClient) -> None:
    put = await client.put(
        "/api/settings/expense_ratios", json={"value": {"INF789F01XA0": 0.19}}
    )
    assert put.status_code == 200

    got = await client.get("/api/settings/expense_ratios")
    assert got.json()["value"] == {"INF789F01XA0": 0.19}

    assert (await client.get("/api/settings/missing")).status_code == 404
