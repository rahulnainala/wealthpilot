"""Request/response models for the Kite auth endpoints."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class LoginUrlResponse(BaseModel):
    login_url: str


class CallbackRequest(BaseModel):
    request_token: str


class SessionStatusResponse(BaseModel):
    """Drives the frontend connection badge / "Reconnect Zerodha" banner."""

    connected: bool
    is_stale: bool = False
    user_id: str | None = None
    session_date: date | None = None
    # Always provided so the UI can offer a one-click reconnect.
    login_url: str


class CallbackResponse(BaseModel):
    connected: bool
    user_id: str
    session_date: date
