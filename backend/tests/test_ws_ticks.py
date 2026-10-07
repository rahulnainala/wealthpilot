"""End-to-end test for the /ws/ticks WebSocket endpoint (mock ticker)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_ws_ticks_streams_mock_ticks() -> None:
    # No `with TestClient(app)` — we skip lifespan (scheduler/seed) since the
    # mock streaming path needs no database.
    client = TestClient(app)
    with client.websocket_connect("/ws/ticks") as ws:
        message = ws.receive_json()

    assert set(message) >= {"token", "symbol", "ltp", "change_pct", "ts"}
    assert isinstance(message["ltp"], (int, float))
    assert message["ltp"] > 0
