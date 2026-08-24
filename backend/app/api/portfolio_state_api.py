from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from app.auth.security import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.security.credential_encryption import decrypt_credentials
from app.brokers.upstox_client import UpstoxClient
from app.portfolio_state import normalize_portfolio

router = APIRouter(prefix="/broker-accounts", tags=["portfolio-state"])

@router.get("/{account_id}/portfolio-state")
def portfolio_state(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.query(BrokerAccount).filter(BrokerAccount.id == account_id, BrokerAccount.user_id == current_user.id).first()
    if not row:
        raise HTTPException(404, "broker account not found")
    if row.broker.lower() != "upstox":
        raise HTTPException(400, "portfolio state is not implemented for this broker")
    credentials = json.loads(decrypt_credentials(row.encrypted_credentials))
    token = credentials.get("access_token") or credentials.get("accessToken")
    if not token:
        raise HTTPException(400, "broker account has no access token")
    client = UpstoxClient(token)
    profile, positions, holdings = client.get_profile(), client.get_positions(), client.get_holdings()
    state = normalize_portfolio(account_id, profile, positions, holdings)
    state.fetched_at = datetime.now(timezone.utc).isoformat()
    return {
        "broker": state.broker,
        "account_id": state.account_id,
        "profile": state.profile,
        "positions": [p.__dict__ for p in state.positions],
        "holdings": [h.__dict__ for h in state.holdings],
        "net_exposure": state.net_exposure,
        "unrealized_pnl": state.unrealized_pnl,
        "fetched_at": state.fetched_at,
    }
