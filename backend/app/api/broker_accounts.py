from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.auth.security import get_current_user
from app.security.credential_encryption import encrypt_credentials
from app.broker_factory import provision_active_account_routes, account_route_name

router = APIRouter(prefix="/broker-accounts", tags=["broker-accounts"])


class BrokerAccountCreate(BaseModel):
    broker: str = Field(min_length=2, max_length=40)
    account_label: str = Field(min_length=1, max_length=80)
    credentials: str = Field(min_length=1, max_length=3000)


class BrokerAccountUpdate(BaseModel):
    credentials: str | None = Field(default=None, min_length=1, max_length=3000)
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


_TERMINAL_ORDER_STATUSES = {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED"}


def _sync_routes(request: Request, db: Session) -> list[str]:
    router = getattr(request.app.state, "broker_router", None)
    if router is None:
        raise HTTPException(503, "broker route manager unavailable")
    return provision_active_account_routes(db, router)


def _ensure_account_safe_to_delete(request: Request, account: BrokerAccount) -> None:
    """Fail closed unless authoritative broker state proves the account is flat."""
    if str(account.status).strip().lower() != "disabled":
        raise HTTPException(409, "disable broker account before deletion")

    router = getattr(request.app.state, "broker_router", None)
    if router is None:
        raise HTTPException(503, "broker route manager unavailable")
    try:
        route = account_route_name(account)
        positions = router.get_positions(route)
        position_rows = positions.require_authoritative() if hasattr(positions, "require_authoritative") else positions
        for row in position_rows:
            quantity = float(row.get("quantity", row.get("net_quantity", 0)) or 0)
            if abs(quantity) > 1e-9:
                raise HTTPException(409, "broker account has open positions")

        broker_route = router.get(route)
        snapshot_fn = getattr(broker_route.adapter, "get_order_snapshot", None)
        if snapshot_fn is None:
            raise HTTPException(503, "authoritative broker order snapshot is required before account deletion")
        orders = snapshot_fn().require_authoritative()
        for order in orders:
            status = str(order.get("status", "")).strip().upper()
            if status not in _TERMINAL_ORDER_STATUSES:
                raise HTTPException(409, "broker account has non-terminal orders")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "unable to verify broker account state before deletion") from exc


def _delete_account_with_route_fence(request: Request, db: Session, account: BrokerAccount) -> None:
    """Remove the account route before DB deletion and restore it if the DB commit fails."""
    router = getattr(request.app.state, "broker_router", None)
    if router is None:
        raise HTTPException(503, "broker route manager unavailable")
    route_name = account_route_name(account)
    with router.route_lifecycle_lock():
        route = router.routes.get(route_name)
        if route is None:
            raise HTTPException(503, "broker account route is not registered")
        if route.broker_account_id != int(account.id):
            raise HTTPException(503, "broker account route identity mismatch")
        if not route.enabled:
            raise HTTPException(503, "broker account route is disabled")

        router.routes.pop(route_name, None)
        try:
            db.delete(account)
            db.commit()
        except Exception as exc:
            db.rollback()
            try:
                router.routes[route_name] = route
            except Exception as restore_error:
                safety_store = getattr(router, "safety_store", None)
                if safety_store is not None:
                    safety_store.halt(f"broker account route restoration failed after DB delete failure: {restore_error}")
                raise HTTPException(500, "broker account deletion failed and route restoration failed; trading halted") from restore_error
            raise HTTPException(500, "broker account deletion failed; route restored") from exc


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
    _ensure_account_safe_to_delete(request, row)
    _delete_account_with_route_fence(request, db, row)
    return {"deleted": True, "id": account_id}
