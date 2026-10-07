"""Tests for daily token-expiry handling and the not-connected path."""

from __future__ import annotations

import pytest
from kiteconnect.exceptions import TokenException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_kite_service
from app.services.kite import KiteNotConnected, KiteTokenExpired
from app.services.kite.real import KiteService


class _FakeKiteRaisingOnRead:
    def holdings(self) -> list[dict[str, object]]:
        raise TokenException("token expired")


class _FakeKiteRaisingOnExchange:
    def generate_session(self, request_token: str, api_secret: str) -> dict[str, str]:
        raise TokenException("invalid request token")


async def test_read_maps_token_exception_to_domain_error() -> None:
    svc = KiteService("api-key", "api-secret")
    svc._kite = _FakeKiteRaisingOnRead()  # type: ignore[assignment]
    with pytest.raises(KiteTokenExpired):
        await svc.get_holdings()


def test_exchange_maps_token_exception_to_domain_error() -> None:
    svc = KiteService("api-key", "api-secret")
    svc._kite = _FakeKiteRaisingOnExchange()  # type: ignore[assignment]
    with pytest.raises(KiteTokenExpired):
        svc.exchange_token("bad-token")


async def test_live_mode_without_session_raises_not_connected(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "use_mock_kite", False)
    with pytest.raises(KiteNotConnected):
        await get_kite_service(db_session)
