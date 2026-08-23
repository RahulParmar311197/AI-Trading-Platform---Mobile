from fastapi import APIRouter

from app.main import recovery_manager

router = APIRouter(prefix="/api/recovery", tags=["recovery"])


@router.get("/status")
def status():
    state = recovery_manager.safety_store.load()
    return {
        "trading_halted": recovery_manager.trading_halted or state.trading_halted,
        "halt_reason": state.halt_reason,
        "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
        "recovery_manager": "ready",
    }
