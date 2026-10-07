"""Integration tests for POST /api/goals/{id}/simulate (mock risk client)."""

from __future__ import annotations

from httpx import AsyncClient


async def _create_goal(client: AsyncClient, **fields: object) -> int:
    payload = {"key": "car", "name": "Car", **fields}
    resp = await client.post("/api/goals", json=payload)
    assert resp.status_code == 201
    return int(resp.json()["id"])


async def test_simulate_then_shows_in_analysis(client: AsyncClient) -> None:
    await client.post("/api/snapshots/refresh")  # provides holdings
    goal_id = await _create_goal(
        client,
        target_date="2032-01-01",
        target_value=1_000_000,
        monthly_contribution=10_000,
        assigned_buckets=["growth", "dividend"],
    )

    resp = await client.post(f"/api/goals/{goal_id}/simulate")
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["probability_of_success"] <= 1.0
    assert body["median_ending_value"] > 0

    analysis = await client.get("/api/analytics/goals")
    car = next(g for g in analysis.json() if g["key"] == "car")
    assert car["simulation"] is not None
    assert car["simulation"]["p90_value"] >= car["simulation"]["p10_value"]


async def test_simulate_with_overrides(client: AsyncClient) -> None:
    goal_id = await _create_goal(
        client, target_date="2032-01-01", target_value=1_000_000
    )
    resp = await client.post(
        f"/api/goals/{goal_id}/simulate",
        json={"monthly_contribution": 50_000, "num_paths": 2_000, "seed": 7},
    )
    assert resp.status_code == 200


async def test_simulate_422_without_target(client: AsyncClient) -> None:
    goal_id = await _create_goal(client, key="notarget", name="No Target")
    resp = await client.post(f"/api/goals/{goal_id}/simulate")
    assert resp.status_code == 422


async def test_simulate_404_missing_goal(client: AsyncClient) -> None:
    resp = await client.post("/api/goals/9999/simulate")
    assert resp.status_code == 404


async def test_stress_endpoint(client: AsyncClient) -> None:
    await client.post("/api/snapshots/refresh")  # provides holdings
    goal_id = await _create_goal(
        client,
        target_date="2032-01-01",
        target_value=1_000_000,
        monthly_contribution=20_000,
        assigned_buckets=["growth", "dividend"],
    )

    resp = await client.post(f"/api/goals/{goal_id}/stress")
    assert resp.status_code == 200
    body = resp.json()
    scenarios = body["scenarios"]
    assert len(scenarios) == 5
    assert scenarios[0]["shock"] == 0.0
    assert body["baseline_probability"] == scenarios[0]["probability_of_success"]

    # Deeper crash -> lower (never higher) probability and median.
    probs = [s["probability_of_success"] for s in scenarios]
    medians = [s["median_ending_value"] for s in scenarios]
    assert probs == sorted(probs, reverse=True)
    assert medians[-1] <= medians[0]


async def test_stress_422_without_target(client: AsyncClient) -> None:
    goal_id = await _create_goal(client, key="notarget", name="No Target")
    resp = await client.post(f"/api/goals/{goal_id}/stress")
    assert resp.status_code == 422


async def test_required_contribution_endpoint(client: AsyncClient) -> None:
    goal_id = await _create_goal(
        client,
        target_date="2032-01-01",
        target_value=5_000_000,
        assigned_buckets=["growth"],
    )
    resp = await client.post(
        f"/api/goals/{goal_id}/required-contribution",
        json={"target_probability": 0.75},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["required_monthly_contribution"] >= 0
    assert isinstance(body["reachable"], bool)
    assert body["target_probability"] == 0.75
