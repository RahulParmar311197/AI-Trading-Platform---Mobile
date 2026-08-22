from dataclasses import dataclass

@dataclass(frozen=True)
class PositionRisk:
    symbol: str
    notional: float
    weight: float

@dataclass(frozen=True)
class PortfolioRisk:
    gross_exposure: float
    concentration: float
    allowed: bool
    reasons: list[str]

def evaluate_portfolio(positions: list[PositionRisk], equity: float, max_gross: float = 2.0, max_single: float = 0.35) -> PortfolioRisk:
    if equity <= 0:
        return PortfolioRisk(0, 1, False, ["equity must be positive"])
    gross = sum(abs(p.notional) for p in positions) / equity
    concentration = max((abs(p.notional) / equity for p in positions), default=0.0)
    reasons = []
    if gross > max_gross: reasons.append("gross exposure limit")
    if concentration > max_single: reasons.append("single-position concentration limit")
    return PortfolioRisk(gross, concentration, not reasons, reasons)
