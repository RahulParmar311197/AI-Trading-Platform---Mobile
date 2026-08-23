from fastapi import APIRouter
from app.provider_bootstrap import build_provider_registry
router=APIRouter(prefix="/api/provider-bootstrap",tags=["provider-bootstrap"])
@router.get("/health")
def health():
    registry=build_provider_registry()
    return {"status":"ok","providers":registry.names()}
