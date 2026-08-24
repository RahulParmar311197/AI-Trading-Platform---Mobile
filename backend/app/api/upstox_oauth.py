import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth.security import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.broker_oauth_state import BrokerOAuthState
from app.security.credential_encryption import encrypt_credentials
from app.brokers.upstox_oauth import new_state, state_hash, authorization_url, exchange_code, expires_at
router = APIRouter(prefix="/broker-accounts/upstox", tags=["broker-oauth"])
@router.get("/oauth/start")
def start(account_label: str = "Upstox", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    settings = get_settings()
    if not settings.upstox_client_id or not settings.upstox_redirect_uri: raise HTTPException(503, "Upstox OAuth is not configured")
    state = new_state(); db.add(BrokerOAuthState(user_id=current_user.id, broker="upstox", account_label=account_label.strip() or "Upstox", state_hash=state_hash(state), expires_at=expires_at())); db.commit()
    return {"authorization_url": authorization_url(settings.upstox_client_id, settings.upstox_redirect_uri, state)}
@router.get("/oauth/callback")
def callback(code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    if error: raise HTTPException(400, f"Upstox authorization failed: {error}")
    if not code or not state: raise HTTPException(400, "missing OAuth code or state")
    row = db.query(BrokerOAuthState).filter(BrokerOAuthState.state_hash == state_hash(state), BrokerOAuthState.used == False).first()
    if not row or row.expires_at < datetime.now(timezone.utc): raise HTTPException(400, "invalid or expired OAuth state")
    row.used = True; settings = get_settings()
    try: token = exchange_code(code, settings.upstox_client_id, settings.upstox_client_secret, settings.upstox_redirect_uri)
    except Exception as exc: db.commit(); raise HTTPException(502, "Upstox token exchange failed") from exc
    access_token = token.get("access_token")
    if not access_token: db.commit(); raise HTTPException(502, "Upstox did not return an access token")
    creds = {"access_token": access_token}
    if token.get("extended_token"): creds["extended_token"] = token["extended_token"]
    account = db.query(BrokerAccount).filter_by(user_id=row.user_id, broker="upstox", account_label=row.account_label).first()
    encrypted = encrypt_credentials(json.dumps(creds))
    if account: account.encrypted_credentials = encrypted; account.status = "active"
    else: db.add(BrokerAccount(user_id=row.user_id, broker="upstox", account_label=row.account_label, encrypted_credentials=encrypted, status="active"))
    db.commit(); return {"connected": True, "broker": "upstox", "account_label": row.account_label}
