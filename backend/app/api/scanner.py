from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.scanner import scan

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


class ScanRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=200)
    timeframes: list[str] = Field(default_factory=lambda: ["15m", "1h", "4h"])
    minimum_score: float = Field(default=1.5, ge=0, le=5)


@router.post("")
def run_scan(payload: ScanRequest):
    return {"results": scan(payload.symbols, payload.timeframes, payload.minimum_score)}
