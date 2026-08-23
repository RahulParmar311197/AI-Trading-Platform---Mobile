from fastapi import APIRouter
from pydantic import BaseModel
from app.risk.portfolio import PositionRisk, evaluate_portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

class Position(BaseModel):
    symbol: str
    notional: float

class PortfolioRequest(BaseModel):
    equity: float
    positions: list[Position]

@router.post("/risk")
def portfolio_risk(body: PortfolioRequest):
    result = evaluate_portfolio([PositionRisk(p.symbol, p.notional, 0) for p in body.positions], body.equity)
    return result.__dict__
