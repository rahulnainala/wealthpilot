"""Symmetric encryption for secrets at rest (the Kite access token).

Uses Fernet (AES-128-CBC + HMAC) with a key supplied via the FERNET_KEY env var.
The Kite access token is short-lived (expires daily ~6 AM IST) but is still a
bearer credential, so it is never persisted in plaintext.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class TokenEncryptionError(RuntimeError):
    """Raised when encryption/decryption cannot be performed."""


def _fernet() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise TokenEncryptionError(
            "FERNET_KEY is not configured. Generate one with "
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"` and set it in the environment.'
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:  # malformed key
        raise TokenEncryptionError("FERNET_KEY is not a valid Fernet key.") from exc


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string, returning a URL-safe base64 token string."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt`.

    Raises :class:`TokenEncryptionError` if the token is invalid or was
    encrypted under a different key.
    """
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise TokenEncryptionError(
            "Stored token could not be decrypted (wrong or rotated FERNET_KEY)."
        ) from exc
