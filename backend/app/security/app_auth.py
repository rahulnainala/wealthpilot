"""Phase 40 — app-level auth (single user).

A password (APP_PASSWORD env) gates the app; a successful login mints a
Fernet-signed session token carrying an expiry (reuses the existing crypto — no
new deps). When APP_PASSWORD is unset (local/mock), auth is disabled and the app
stays open. Required before execution (Wave J) and public deploy.
"""

from __future__ import annotations

import hmac
import json
import time

from app.config import get_settings
from app.security.crypto import decrypt, encrypt

_TTL_SECONDS = 7 * 24 * 3600  # a week


def auth_enabled() -> bool:
    return bool(get_settings().app_password)


def check_password(password: str) -> bool:
    expected = get_settings().app_password or ""
    return bool(expected) and hmac.compare_digest(password, expected)


def create_session_token() -> str:
    payload = json.dumps({"sub": "owner", "exp": int(time.time()) + _TTL_SECONDS})
    return encrypt(payload)


def verify_session_token(token: str) -> bool:
    try:
        payload = json.loads(decrypt(token))
    except Exception:  # noqa: BLE001 — any decrypt/parse failure = invalid
        return False
    return payload.get("sub") == "owner" and float(payload.get("exp", 0)) > time.time()
