from fastapi import APIRouter, HTTPException
from app.provider_bootstrap import build_provider_registry
router=APIRouter(prefix="/api/providers",tags=["data-provider"])
@router.get("/health")
def provider_health():
    try:
        registry=build_provider_registry()
        return {"status":"ok","providers":registry.names()}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=str(exc)) from exc
@router.get("")
def providers():
    try:
        registry=build_provider_registry()
        return {"providers":registry.names()}
    except Exception as exc:
        raise HTTPException(status_code=503,detail=str(exc)) from exc
