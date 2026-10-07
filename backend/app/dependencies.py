"""Shared FastAPI dependencies (DB session, Kite service resolution)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.security.crypto import decrypt
from app.services.kite import BaseKiteService, KiteNotConnected, build_kite_service
from app.services.kite_sessions import get_active_session
from app.services.risk import BaseRiskClient, get_risk_client

DbSession = Annotated[AsyncSession, Depends(get_db)]
RiskDep = Annotated[BaseRiskClient, Depends(get_risk_client)]


async def get_kite_service(db: DbSession) -> BaseKiteService:
    """Resolve an authenticated Kite service for the active session.

    In mock mode no session is required. In live mode, the most recent
    non-stale session's token is decrypted and injected; if there is none, a
    :class:`KiteNotConnected` is raised (surfaced to the frontend as a
    reconnect prompt).
    """
    if get_settings().use_mock_kite:
        return build_kite_service()

    session = await get_active_session(db)
    if session is None:
        raise KiteNotConnected("No active Zerodha session. Please reconnect.")
    access_token = decrypt(session.access_token_encrypted)
    return build_kite_service(access_token=access_token)


KiteDep = Annotated[BaseKiteService, Depends(get_kite_service)]


async def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Phase 40/42: 401 unless a valid session token is present (when auth is on).

    Applied to execution endpoints for defense-in-depth on top of the middleware.
    """
    from app.security.app_auth import auth_enabled, verify_session_token

    if not auth_enabled():
        return
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not verify_session_token(token):
        raise HTTPException(status_code=401, detail="auth_required")


RequireAuth = Annotated[None, Depends(require_auth)]
