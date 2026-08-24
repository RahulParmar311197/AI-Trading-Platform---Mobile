from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquitySnapshot:
    """Authoritative inputs needed to calculate an account equity snapshot."""

    starting_equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    fees: float = 0.0
    charges: float = 0.0

    @property
    def equity(self) -> float:
        return self.starting_equity + self.realized_pnl + self.unrealized_pnl - self.fees - self.charges

    @property
    def net_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl - self.fees - self.charges

    def validate(self) -> None:
        values = {
            "starting_equity": self.starting_equity,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "fees": self.fees,
            "charges": self.charges,
        }
        for name, value in values.items():
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid {name}") from exc
            if number != number or number in (float("inf"), float("-inf")):
                raise ValueError(f"invalid {name}")
        if float(self.starting_equity) < 0:
            raise ValueError("starting_equity cannot be negative")
        if float(self.fees) < 0 or float(self.charges) < 0:
            raise ValueError("fees and charges cannot be negative")


def calculate_equity(*, starting_equity: float, realized_pnl: float = 0.0,
                     unrealized_pnl: float = 0.0, fees: float = 0.0,
                     charges: float = 0.0) -> float:
    snapshot = EquitySnapshot(starting_equity, realized_pnl, unrealized_pnl, fees, charges)
    snapshot.validate()
    return snapshot.equity
