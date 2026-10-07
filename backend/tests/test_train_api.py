"""Integration tests for the /api/ai/train/* endpoints ("Push to 3070").

Monkeypatches the generator itself (same stand-in as test_train_runner.py) so
these exercise the HTTP layer without touching the DB/Ollama in the
background task.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.services.ai import train_runner


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    train_runner.stop()
    await asyncio.sleep(0)


async def test_start_then_status_then_stop(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run(target: int, concurrency: int, model: str | None) -> None:
        await asyncio.sleep(10)

    monkeypatch.setattr(train_runner, "run_generation", fake_run)

    start_resp = await client.post("/api/ai/train/start")
    assert start_resp.status_code == 200
    assert start_resp.json() == {"running": True}
    assert train_runner.is_running() is True

    status_resp = await client.get("/api/ai/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["training_generator_running"] is True

    stop_resp = await client.post("/api/ai/train/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json() == {"running": False}

    await asyncio.sleep(0)
    assert train_runner.is_running() is False


async def test_status_shows_not_running_by_default(client: AsyncClient) -> None:
    resp = await client.get("/api/ai/status")
    assert resp.status_code == 200
    assert resp.json()["training_generator_running"] is False
