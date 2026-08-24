from __future__ import annotations

from dataclasses import dataclass
from random import Random
from statistics import mean
from typing import Sequence


@dataclass(frozen=True)
class MonteCarloConfig:
    simulations: int = 2000
    seed: int = 42


@dataclass(frozen=True)
class MonteCarloResult:
    simulations: int
    median_final_equity: float
    worst_final_equity: float
    best_final_equity: float
    median_max_drawdown: float
    worst_max_drawdown: float
    probability_of_loss: float
    probability_of_ruin: float


class MonteCarloAnalyzer:
    """Randomizes the order of realized trade P&Ls to test path dependence."""

    def __init__(self, config: MonteCarloConfig | None = None):
        self.config = config or MonteCarloConfig()
        if self.config.simulations <= 0:
            raise ValueError("simulations must be positive")

    def analyze(self, initial_equity: float, trade_pnls: Sequence[float], ruin_fraction: float = 0.50) -> MonteCarloResult:
        if initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if not 0 < ruin_fraction <= 1:
            raise ValueError("ruin_fraction must be in (0, 1]")
        if not trade_pnls:
            return MonteCarloResult(0, initial_equity, initial_equity, initial_equity, 0.0, 0.0, 0.0, 0.0)
        rng = Random(self.config.seed)
        finals=[]; drawdowns=[]; losses=0; ruins=0
        for _ in range(self.config.simulations):
            sequence=list(trade_pnls); rng.shuffle(sequence)
            equity=initial_equity; peak=equity; max_dd=0.0
            for pnl in sequence:
                equity += pnl
                peak=max(peak,equity)
                max_dd=max(max_dd, peak-equity)
            finals.append(equity); drawdowns.append(max_dd)
            losses += equity < initial_equity
            ruins += equity <= initial_equity * ruin_fraction
        finals.sort(); drawdowns.sort()
        mid=len(finals)//2
        return MonteCarloResult(
            self.config.simulations,
            finals[mid],
            finals[0],
            finals[-1],
            drawdowns[mid],
            drawdowns[-1],
            losses/self.config.simulations,
            ruins/self.config.simulations,
        )
