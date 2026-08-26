from __future__ import annotations

from fastapi import Header, HTTPException

from app.auth.session import SessionAuthenticator, UserSession


def current_user(authorization: str | None = Header(default=None)) -> UserSession:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        return SessionAuthenticator().verify(authorization[7:].strip())
    except (RuntimeError, ValueError):
        raise HTTPException(status_code=401, detail="invalid or expired session")
