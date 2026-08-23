from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.trade_journal import JournalTrade, journal, now_iso

router = APIRouter(prefix="/api/journal", tags=["trade-journal"])


class TradeRequest(BaseModel):
    id: str
    symbol: str
    side: str = Field(pattern="^(BUY|SELL)$")
    entry: float = Field(gt=0)
    exit: float = Field(gt=0)
    quantity: float = Field(gt=0)
    pnl: float
    setup_score: float = 0
    strategy: str = "ICT_CONFLUENCE"
    opened_at: str | None = None
    closed_at: str | None = None
    exit_reason: str = ""


@router.post("/trades", status_code=201)
def record_trade(payload: TradeRequest):
    trade = JournalTrade(**payload.model_dump(), opened_at=payload.opened_at or now_iso(), closed_at=payload.closed_at or now_iso())
    return journal.record(trade).__dict__


@router.get("/trades")
def trades():
    return journal.all()


@router.get("/summary")
def summary():
    return journal.summary()
