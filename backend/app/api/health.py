from fastapi import APIRouter
router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {"api": "ok", "market_data": "demo", "risk_engine": "ok"}
