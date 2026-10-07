"""Tests for Fernet encryption of secrets at rest."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.security.crypto import TokenEncryptionError, decrypt, encrypt


def test_encrypt_decrypt_roundtrip() -> None:
    token = "kite-access-token-xyz"
    ciphertext = encrypt(token)
    assert ciphertext != token
    assert decrypt(ciphertext) == token


def test_decrypt_with_rotated_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    ciphertext = encrypt("secret")
    settings = get_settings()
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    with pytest.raises(TokenEncryptionError):
        decrypt(ciphertext)


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "fernet_key", None)
    with pytest.raises(TokenEncryptionError):
        encrypt("anything")
