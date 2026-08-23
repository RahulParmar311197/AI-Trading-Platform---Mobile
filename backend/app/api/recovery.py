from fastapi import APIRouter

router = APIRouter(prefix="/api/recovery", tags=["recovery"])


def _manager():
    # Lazy import avoids an app.main <-> api.recovery import cycle.
    from app.main import recovery_manager

    return recovery_manager


@router.get("/status")
def status():
    manager = _manager()
    state = manager.safety_store.load()
    return {
        "trading_halted": manager.trading_halted or state.trading_halted,
        "halt_reason": state.halt_reason,
        "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
        "recovery_manager": "ready",
    }
