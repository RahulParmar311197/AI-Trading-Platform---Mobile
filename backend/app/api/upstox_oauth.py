import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.broker_factory import provision_active_account_routes, validate_active_account_routes
from app.api.broker_accounts import _create_account_with_route_fence, _quarantine_account_after_route_validation_failure, _update_account_with_route_fence
from app.brokers.upstox_oauth import authorization_url, exchange_code, expires_at, new_state, state_hash, validate_token_response
from app.config import get_settings
from app.db import get_db
from app.models.broker_account import BrokerAccount
from app.models.broker_oauth_state import BrokerOAuthState
from app.models.user import User

router = APIRouter(prefix="/broker-accounts/upstox", tags=["broker-oauth"])


@router.get("/oauth/start")
def start(account_label: str = "Upstox", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    settings = get_settings()
    label = account_label.strip()
    if not label or len(label) > 80:
        raise HTTPException(400, "account_label is required and must be at most 80 characters")
    if not settings.upstox_client_id or not settings.upstox_redirect_uri:
        raise HTTPException(503, "Upstox OAuth is not configured")
    state = new_state()
    db.add(BrokerOAuthState(user_id=current_user.id, broker="upstox", account_label=label, state_hash=state_hash(state), expires_at=expires_at(), used=False))
    db.commit()
    return {"authorization_url": authorization_url(settings.upstox_client_id, settings.upstox_redirect_uri, state)}


@router.get("/oauth/callback")
def callback(code: str | None = None, state: str | None = None, error: str | None = None, request: Request = None, db: Session = Depends(get_db)):
    if error:
        raise HTTPException(400, "Upstox authorization was declined or failed")
    if not code or not state:
        raise HTTPException(400, "missing OAuth code or state")
    now = datetime.now(timezone.utc)
    row = db.query(BrokerOAuthState).filter(BrokerOAuthState.state_hash == state_hash(state), BrokerOAuthState.broker == "upstox", BrokerOAuthState.used.is_(False), BrokerOAuthState.expires_at > now).first()
    if row is None:
        raise HTTPException(400, "invalid, expired, or already-used OAuth state")
    consumed = db.execute(update(BrokerOAuthState).where(BrokerOAuthState.id == row.id, BrokerOAuthState.used.is_(False), BrokerOAuthState.expires_at > now).values(used=True))
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(400, "invalid, expired, or already-used OAuth state")
    db.commit()

    settings = get_settings()
    try:
        token = exchange_code(code, settings.upstox_client_id, settings.upstox_client_secret, settings.upstox_redirect_uri)
        identity = validate_token_response(token)
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Upstox token exchange failed") from exc

    credentials = {"access_token": identity["access_token"], "broker_user_id": identity["broker_user_id"], "broker": identity["broker"]}
    if token.get("extended_token"):
        credentials["extended_token"] = token["extended_token"]
    credentials_json = json.dumps(credentials, separators=(",", ":"))

    account = db.query(BrokerAccount).filter_by(user_id=row.user_id, broker="upstox", account_label=row.account_label).first()
    try:
        if account is None:
            account = BrokerAccount(user_id=row.user_id, broker="upstox", account_label=row.account_label, encrypted_credentials="pending", status="active")
            from app.security.credential_encryption import encrypt_credentials
            account.encrypted_credentials = encrypt_credentials(credentials_json)
            _create_account_with_route_fence(request, db, account)
        else:
            _update_account_with_route_fence(request, db, account, credentials=credentials_json, status="active")
    except HTTPException:
        raise

    router_obj = getattr(request.app.state, "broker_router", None) if request else None
    if router_obj is None:
        account.status = "disabled"
        db.commit()
        raise HTTPException(503, "Upstox credentials saved but broker route manager is unavailable; account disabled")

    errors = provision_active_account_routes(db, router_obj)
    errors += validate_active_account_routes(db, router_obj)
    if errors:
        _quarantine_account_after_route_validation_failure(request, db, account, errors)

    return {"connected": True, "broker": "upstox", "account_label": row.account_label, "account_id": account.id, "broker_user_id": identity["broker_user_id"], "status": account.status}