"""Integration tests for the Kite auth endpoints (against MockKiteService)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.crypto import decrypt
from app.services.kite_sessions import get_active_session


async def test_login_returns_url(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/kite/login")
    assert resp.status_code == 200
    assert resp.json()["login_url"].startswith("https://kite.zerodha.com")


async def test_status_disconnected_before_login(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/kite/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is False
    assert body["login_url"]  # always offered for reconnect


async def test_callback_connects_and_stores_encrypted_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/api/auth/kite/callback", json={"request_token": "REQ-TOKEN-1"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["user_id"] == "MOCK123"

    status = await client.get("/api/auth/kite/status")
    assert status.json()["connected"] is True
    assert status.json()["is_stale"] is False

    # Token is persisted encrypted, not in plaintext.
    session = await get_active_session(db_session)
    assert session is not None
    assert session.access_token_encrypted != "mock-access-REQ-TOKEN-1"
    assert decrypt(session.access_token_encrypted) == "mock-access-REQ-TOKEN-1"


async def test_relogin_retires_previous_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/api/auth/kite/callback", json={"request_token": "A"})
    await client.post("/api/auth/kite/callback", json={"request_token": "B"})

    active = await get_active_session(db_session)
    assert active is not None
    assert decrypt(active.access_token_encrypted) == "mock-access-B"
