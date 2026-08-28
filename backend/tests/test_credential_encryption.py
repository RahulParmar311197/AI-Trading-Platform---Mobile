from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

from app.security.credential_encryption import decrypt_credentials, encrypt_credentials


def test_encrypt_decrypt_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROKER_CREDENTIALS_KEY", Fernet.generate_key().decode())
    plaintext = '{"access_token":"secret-token","refresh_token":"secret-refresh"}'

    ciphertext = encrypt_credentials(plaintext)

    assert ciphertext != plaintext
    assert decrypt_credentials(ciphertext) == plaintext


def test_missing_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BROKER_CREDENTIALS_KEY", raising=False)

    with pytest.raises(RuntimeError, match="BROKER_CREDENTIALS_KEY"):
        encrypt_credentials("secret")


def test_invalid_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROKER_CREDENTIALS_KEY", "not-a-fernet-key")

    with pytest.raises(RuntimeError, match="valid Fernet key"):
        encrypt_credentials("secret")


def test_empty_plaintext_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROKER_CREDENTIALS_KEY", Fernet.generate_key().decode())

    with pytest.raises(ValueError, match="cannot be empty"):
        encrypt_credentials("")


def test_malformed_ciphertext_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROKER_CREDENTIALS_KEY", Fernet.generate_key().decode())

    with pytest.raises(Exception):
        decrypt_credentials("not-valid-ciphertext")
