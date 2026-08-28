import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.broker_factory import account_route_name, build_account_route, provision_active_account_routes
from app.brokers.upstox_oauth import authorization_url, exchange_code, expires_at, new_state, state_hash
from app.config import get_settings
from app.db import get_db
from app.models.broker_account import BrokerAccount
from app.models.broker_oauth_state import BrokerOAuthState
from app.models.user import User
from app.security.credential_encryption import encrypt_credentials

router = APIRouter(prefix="/broker-accounts/upstox", tags=["broker-oauth"])


@router.get("/oauth/start")
def start(
    account_label: str = "Upstox",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    label = account_label.strip()
    if not label or len(label) > 80:
        raise HTTPException(400, "account_label is required and must be at most 80 characters")
    if not settings.upstox_client_id or not settings.upstox_redirect_uri:
        raise HTTPException(503, "Upstox OAuth is not configured")

    state = new_state()
    db.add(
        BrokerOAuthState(
            user_id=current_user.id,
            broker="upstox",
            account_label=label,
            state_hash=state_hash(state),
            expires_at=expires_at(),
            used=False,
        )
    )
    db.commit()
    return {
        "authorization_url": authorization_url(
            settings.upstox_client_id, settings.upstox_redirect_uri, state
        )
    }


@router.get("/oauth/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    request: Request | None = None,
    db: Session = Depends(get_db),
):
    if error:
        raise HTTPException(400, "Upstox authorization was declined or failed")
    if not code or not state:
        raise HTTPException(400, "missing OAuth code or state")

    digest = state_hash(state)
    now = datetime.now(timezone.utc)

    # Consume the state atomically. This prevents two concurrent callbacks from
    # exchanging the same authorization code/state pair.
    row = db.query(BrokerOAuthState).filter(
        BrokerOAuthState.state_hash == digest,
        BrokerOAuthState.broker == "upstox",
        BrokerOAuthState.used.is_(False),
        BrokerOAuthState.expires_at > now,
    ).first()
    if row is None:
        raise HTTPException(400, "invalid, expired, or already-used OAuth state")

    consumed = db.execute(
        update(BrokerOAuthState)
        .where(
            BrokerOAuthState.id == row.id,
            BrokerOAuthState.used.is_(False),
            BrokerOAuthState.expires_at > now,
        )
        .values(used=True)
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(400, "invalid, expired, or already-used OAuth state")
    db.commit()

    settings = get_settings()
    try:
        token = exchange_code(
            code,
            settings.upstox_client_id,
            settings.upstox_client_secret,
            settings.upstox_redirect_uri,
        )
    except Exception as exc:
        raise HTTPException(502, "Upstox token exchange failed") from exc

    access_token = str(token.get("access_token", "")).strip()
    if not access_token:
        raise HTTPException(502, "Upstox did not return an access token")

    credentials = {"access_token": access_token}
    if token.get("extended_token"):
        credentials["extended_token"] = token["extended_token"]
    encrypted = encrypt_credentials(json.dumps(credentials))

    account = db.query(BrokerAccount).filter_by(
        user_id=row.user_id,
        broker="upstox",
        account_label=row.account_label,
    ).first()
    if account is None:
        account = BrokerAccount(
            user_id=row.user_id,
            broker="upstox",
            account_label=row.account_label,
            encrypted_credentials=encrypted,
            status="active",
        )
        db.add(account)
    else:
        account.encrypted_credentials = encrypted
        account.status = "active"
    db.commit()
    db.refresh(account)

    # Do not expose the account as tradable unless the same route machinery used
    # at startup can successfully construct and validate it.
    try:
        router_obj = getattr(request.app.state, "broker_router", None) if request else None
        if router_obj is None:
            raise RuntimeError("broker route manager unavailable")
        errors = provision_active_account_routes(db, router_obj)
        if errors:
            account.status = "disabled"
            db.commit()
            router_obj.routes.pop(account_route_name(account), None)
            raise HTTPException(503, {"message": "Upstox credentials saved but account was disabled because route provisioning failed", "errors": errors})
    except HTTPException:
        raise
    except Exception as exc:
        account.status = "disabled"
        db.commit()
        raise HTTPException(503, "Upstox credentials saved but account was disabled because route provisioning failed") from exc

    return {
        "connected": True,
        "broker": "upstox",
        "account_label": row.account_label,
        "account_id": account.id,
        "status": account.status,
    }
