from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.auth.security import get_current_user
from app.security.credential_encryption import encrypt_credentials

router = APIRouter(prefix="/broker-accounts", tags=["broker-accounts"])

class BrokerAccountCreate(BaseModel):
    broker: str = Field(min_length=2, max_length=40)
    account_label: str = Field(min_length=1, max_length=80)
    credentials: str = Field(min_length=1, max_length=3000)

@router.post("")
def create_account(body: BrokerAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker, label = body.broker.strip(), body.account_label.strip()
    if db.query(BrokerAccount).filter_by(user_id=current_user.id, broker=broker, account_label=label).first():
        raise HTTPException(409, "broker account already exists")
    account = BrokerAccount(user_id=current_user.id, broker=broker, account_label=label, encrypted_credentials=encrypt_credentials(body.credentials), status="active")
    db.add(account); db.commit(); db.refresh(account)
    return {"id": account.id, "broker": account.broker, "account_label": account.account_label, "status": account.status}

@router.get("")
def list_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(BrokerAccount).filter(BrokerAccount.user_id == current_user.id).all()
    return [{"id": r.id, "broker": r.broker, "account_label": r.account_label, "status": r.status} for r in rows]

@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.query(BrokerAccount).filter(BrokerAccount.id == account_id, BrokerAccount.user_id == current_user.id).first()
    if not row: raise HTTPException(404, "broker account not found")
    db.delete(row); db.commit()
    return {"deleted": True, "id": account_id}
