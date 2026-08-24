from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from app.auth.security import get_current_user
from app.db import get_db
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.security.credential_encryption import decrypt_credentials
from app.brokers.upstox_client import UpstoxClient
router = APIRouter(prefix="/broker-accounts", tags=["broker-account-state"])
def _account(account_id,db,user):
 row=db.query(BrokerAccount).filter(BrokerAccount.id==account_id,BrokerAccount.user_id==user.id).first()
 if not row: raise HTTPException(404,"broker account not found")
 if row.broker.lower()!="upstox": raise HTTPException(400,"read-only state is not implemented for this broker")
 return row
def _client(row):
 credentials=json.loads(decrypt_credentials(row.encrypted_credentials)); token=credentials.get("access_token") or credentials.get("accessToken")
 if not token: raise HTTPException(400,"broker account has no access token")
 return UpstoxClient(token)
@router.get("/{account_id}/profile")
def profile(account_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)): return _client(_account(account_id,db,current_user)).get_profile()
@router.get("/{account_id}/positions")
def positions(account_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)): return _client(_account(account_id,db,current_user)).get_positions()
@router.get("/{account_id}/holdings")
def holdings(account_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)): return _client(_account(account_id,db,current_user)).get_holdings()
