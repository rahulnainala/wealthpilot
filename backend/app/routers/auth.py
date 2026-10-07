"""Zerodha Kite Connect authentication endpoints.

Login flow:
  1. Frontend fetches ``GET /api/auth/kite/login`` and redirects the user to
     the returned Kite login URL.
  2. Kite redirects back to the frontend callback page with a ``request_token``.
  3. Frontend POSTs that token to ``POST /api/auth/kite/callback``; the backend
     exchanges it for an access token (using the API secret) and stores it
     encrypted, retiring any previous session.
  4. ``GET /api/auth/kite/status`` reports connection state for the UI badge.

Read-only by design — this app never places orders.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.dependencies import DbSession
from app.schemas.auth import (
    CallbackRequest,
    CallbackResponse,
    LoginUrlResponse,
    SessionStatusResponse,
)
from app.services.kite import build_kite_service, reset_kite_cache
from app.services.kite_sessions import get_active_session, store_new_session

router = APIRouter(prefix="/api/auth/kite", tags=["auth"])


@router.get("/login", response_model=LoginUrlResponse)
async def kite_login() -> LoginUrlResponse:
    """Return the Kite Connect login URL to redirect the user to."""
    service = build_kite_service()
    return LoginUrlResponse(login_url=service.get_login_url())


@router.post("/callback", response_model=CallbackResponse)
async def kite_callback(payload: CallbackRequest, db: DbSession) -> CallbackResponse:
    """Exchange a ``request_token`` for an access token and persist it."""
    service = build_kite_service()
    token = service.exchange_token(payload.request_token)  # may raise KiteError
    session = await store_new_session(db, token)
    reset_kite_cache()  # fresh login → drop any stale cached reads
    return CallbackResponse(
        connected=True,
        user_id=session.kite_user_id,
        session_date=session.session_date,
    )


@router.get("/status", response_model=SessionStatusResponse)
async def kite_status(db: DbSession) -> SessionStatusResponse:
    """Report whether a live Kite session exists (drives the reconnect banner)."""
    login_url = build_kite_service().get_login_url()
    session = await get_active_session(db)
    if session is None:
        return SessionStatusResponse(connected=False, login_url=login_url)
    return SessionStatusResponse(
        connected=True,
        is_stale=session.is_stale,
        user_id=session.kite_user_id,
        session_date=session.session_date,
        login_url=login_url,
    )


# --- App-level auth (Phase 40): single-user login gating the whole app ---------
app_auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str


@app_auth_router.get("/config")
async def auth_config() -> dict[str, bool]:
    from app.security.app_auth import auth_enabled

    return {"auth_enabled": auth_enabled()}


@app_auth_router.post("/login", response_model=TokenResponse)
async def app_login(payload: LoginRequest) -> TokenResponse:
    from app.security.app_auth import auth_enabled, check_password, create_session_token

    if auth_enabled() and not check_password(payload.password):
        raise HTTPException(status_code=401, detail="invalid_password")
    return TokenResponse(token=create_session_token())


@app_auth_router.get("/me")
async def app_me(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    from app.security.app_auth import auth_enabled, verify_session_token

    if not auth_enabled():
        return {"ok": True}
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not verify_session_token(token):
        raise HTTPException(status_code=401, detail="auth_required")
    return {"ok": True}
