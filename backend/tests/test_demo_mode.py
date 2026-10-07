"""Public demo: read-only, mock-only, and no key survives a misconfigured env."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from app.config import Settings, get_settings


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("DEMO_MODE")
    get_settings.cache_clear()


def test_demo_drops_real_sources_and_keys() -> None:
    s = Settings(
        demo_mode=True,
        use_mock_kite=False,
        market_data_provider="yahoo",
        app_password="pw",
        anthropic_api_key="sk-real",
        ollama_url="http://10.0.0.2:11434",
        vapid_private_key="k",
    )
    assert s.use_mock_kite is True
    assert s.market_data_provider == "mock"
    assert (s.app_password, s.anthropic_api_key, s.ollama_url, s.vapid_private_key) == (
        None,
        None,
        None,
        None,
    )


@pytest.mark.usefixtures("demo")
async def test_demo_refuses_writes(client: AsyncClient) -> None:
    for method, path in [
        ("POST", "/api/goals"),
        ("PUT", "/api/goals/1"),
        ("DELETE", "/api/goals/1"),
        ("POST", "/api/execution/gtt"),
        ("POST", "/api/snapshots/refresh"),
        ("POST", "/api/chat"),
    ]:
        resp = await client.request(method, path, json={})
        assert resp.status_code == 403, (method, path)
        assert resp.json() == {"error": "read_only_demo"}


@pytest.mark.usefixtures("demo")
async def test_demo_allows_reads_and_calculations(client: AsyncClient) -> None:
    assert (await client.get("/api/goals")).status_code == 200
    # A calculation is not a write: it gets past the guard to the route, which
    # 404s here only because the test DB has no goal 1.
    resp = await client.post("/api/goals/1/simulate", json={"num_paths": 200_000})
    assert resp.status_code == 404


async def test_writes_open_outside_demo(client: AsyncClient) -> None:
    resp = await client.post("/api/goals", json={"key": "x", "name": "X"})
    assert resp.status_code != 403
