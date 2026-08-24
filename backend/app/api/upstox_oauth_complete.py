from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auth.security import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.broker_oauth_state import BrokerOAuthState
from app.brokers.upstox_oauth import exchange_code_for_token
from app.security.credential_encryption import encrypt_credentials

router = APIRouter(prefix="/broker-accounts/upstox/oauth", tags=["broker-oauth"])

class OAuthComplete(BaseModel):
    code: str
    state: str

@router.post("/complete")
def complete(payload: OAuthComplete, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    state_row = db.query(BrokerOAuthState).filter(BrokerOAuthState.state == payload.state, BrokerOAuthState.user_id == current_user.id).first()
    if not state_row:
        raise HTTPException(400, "invalid or expired OAuth state")
    account_label = state_row.account_label or "Upstox"
    db.delete(state_row)
    db.commit()
    try:
        token = exchange_code_for_token(payload.code)
        account = BrokerAccount(user_id=current_user.id, broker="upstox", account_label=account_label, encrypted_credentials=encrypt_credentials(token))
        db.add(account)
        db.commit()
        db.refresh(account)
        return {"id": account.id, "broker": account.broker, "account_label": account.account_label, "status": "connected"}
    except Exception as exc:
        raise HTTPException(502, f"Upstox authorization failed: {exc}")
