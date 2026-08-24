from datetime import datetime, timedelta, timezone
from hashlib import sha256
import base64
import hmac
import json

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.user import User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    if len(password_hash) == 64 and all(c in "0123456789abcdef" for c in password_hash.lower()):
        return hmac.compare_digest(sha256(password.encode()).hexdigest(), password_hash.lower())
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False


def needs_password_upgrade(password_hash: str) -> bool:
    return len(password_hash or "") == 64 and all(c in "0123456789abcdef" for c in password_hash.lower())


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    if settings.is_production and settings.jwt_secret in {"change-me", "change-me-in-production", ""}:
        raise RuntimeError("JWT_SECRET must be configured in production")
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.jwt_exp_minutes)
    payload = {"sub": str(subject), "exp": int(exp.timestamp())}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret.encode(), raw.encode(), sha256).hexdigest()
    return f"{raw}.{signature}"


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        raw, signature = token.split(".", 1)
        expected = hmac.new(settings.jwt_secret.encode(), raw.encode(), sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid token")
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if payload["exp"] < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired token")
        if not str(payload.get("sub", "")).strip():
            raise ValueError("missing subject")
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("invalid token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHENTICATION_REQUIRED")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_ACCESS_TOKEN")
    username = str(payload["sub"])
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="USER_NOT_FOUND")
    return user
