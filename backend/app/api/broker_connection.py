from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth.security import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.security.credential_encryption import decrypt_credentials
from app.brokers.upstox import UpstoxAdapter
import json

router = APIRouter(prefix="/broker-accounts", tags=["broker-accounts"])

@router.get("/{account_id}/health")
def broker_health(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.query(BrokerAccount).filter(BrokerAccount.id == account_id, BrokerAccount.user_id == current_user.id).first()
    if not row:
        raise HTTPException(404, "broker account not found")
    try:
        credentials = json.loads(decrypt_credentials(row.encrypted_credentials))
        if row.broker.lower() != "upstox":
            return {"id": row.id, "broker": row.broker, "status": "unsupported"}
        result = UpstoxAdapter(credentials).health()
        return {"id": row.id, "broker": row.broker, **result}
    except Exception:
        return {"id": row.id, "broker": row.broker, "configured": False, "live_trading_enabled": False, "status": "connection_failed"}
