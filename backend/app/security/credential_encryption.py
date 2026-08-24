"""Application-level encryption for broker credentials."""
import os
from cryptography.fernet import Fernet

_ENV_KEY = "BROKER_CREDENTIALS_KEY"

def _fernet() -> Fernet:
    key = os.getenv(_ENV_KEY)
    if not key:
        raise RuntimeError(f"{_ENV_KEY} is not configured")
    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise RuntimeError(f"{_ENV_KEY} must contain a valid Fernet key") from exc

def encrypt_credentials(credentials: str) -> str:
    if not credentials:
        raise ValueError("credentials cannot be empty")
    return _fernet().encrypt(credentials.encode()).decode()

def decrypt_credentials(ciphertext: str) -> str:
    if not ciphertext:
        raise ValueError("ciphertext cannot be empty")
    return _fernet().decrypt(ciphertext.encode()).decode()
