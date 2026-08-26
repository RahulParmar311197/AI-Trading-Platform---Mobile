from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.auth.security import get_current_user
from app.security.credential_encryption import encrypt_credentials
from app.broker_factory import provision_active_account_routes

router = APIRouter(prefix="/broker-accounts", tags=["broker-accounts"])


class BrokerAccountCreate(BaseModel):
    broker: str = Field(min_length=2, max_length=40)
    account_label: str = Field(min_length=1, max_length=80)
    credentials: str = Field(min_length=1, max_length=3000)


class BrokerAccountUpdate(BaseModel):
    credentials: str | None = Field(default=None, min_length=1, max_length=3000)
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


def _sync_routes(request: Request, db: Session) -> list[str]:
    router = getattr(request.app.state, "broker_router", None)
    if router is None:
        raise HTTPException(503, "broker route manager unavailable")
    return provision_active_account_routes(db, router)


@router.post("")
def create_account(
    body: BrokerAccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker, label = body.broker.strip(), body.account_label.strip()
    if db.query(BrokerAccount).filter_by(user_id=current_user.id, broker=broker, account_label=label).first():
        raise HTTPException(409, "broker account already exists")
    account = BrokerAccount(
        user_id=current_user.id,
        broker=broker,
        account_label=label,
        encrypted_credentials=encrypt_credentials(body.credentials),
        status="active",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    errors = _sync_routes(request, db)
    if errors:
        db.delete(account)
        db.commit()
        _sync_routes(request, db)
        raise HTTPException(409, {"message": "broker account route provisioning failed", "errors": errors})
    return {"id": account.id, "broker": account.broker, "account_label": account.account_label, "status": account.status}


@router.get("")
def list_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(BrokerAccount).filter(BrokerAccount.user_id == current_user.id).all()
    return [{"id": r.id, "broker": r.broker, "account_label": r.account_label, "status": r.status} for r in rows]


@router.patch("/{account_id}")
def update_account(
    account_id: int,
    body: BrokerAccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(BrokerAccount).filter(BrokerAccount.id == account_id, BrokerAccount.user_id == current_user.id).first()
    if not row:
        raise HTTPException(404, "broker account not found")
    if body.credentials is None and body.status is None:
        raise HTTPException(400, "credentials or status is required")
    if body.credentials is not None:
        row.encrypted_credentials = encrypt_credentials(body.credentials)
    if body.status is not None:
        row.status = body.status
    db.commit()
    db.refresh(row)
    errors = _sync_routes(request, db)
    if errors and row.status == "active":
        row.status = "disabled"
        db.commit()
        _sync_routes(request, db)
        raise HTTPException(409, {"message": "broker account route provisioning failed; account disabled", "errors": errors})
    return {"id": row.id, "broker": row.broker, "account_label": row.account_label, "status": row.status}


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(BrokerAccount).filter(BrokerAccount.id == account_id, BrokerAccount.user_id == current_user.id).first()
    if not row:
        raise HTTPException(404, "broker account not found")
    db.delete(row)
    db.commit()
    errors = _sync_routes(request, db)
    if errors:
        raise HTTPException(500, {"message": "broker route cleanup failed", "errors": errors})
    return {"deleted": True, "id": account_id}
