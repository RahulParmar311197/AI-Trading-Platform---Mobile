from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import base64
import json
from app.core.config import settings

def hash_password(password: str) -> str:
    return sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)

def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.jwt_exp_minutes)
    payload = {"sub": subject, "exp": int(exp.timestamp())}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret.encode(), raw.encode(), sha256).hexdigest()
    return f"{raw}.{signature}"

def decode_access_token(token: str) -> dict:
    raw, signature = token.split(".", 1)
    expected = hmac.new(settings.jwt_secret.encode(), raw.encode(), sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid token")
    payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    if payload["exp"] < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("expired token")
    return payload
