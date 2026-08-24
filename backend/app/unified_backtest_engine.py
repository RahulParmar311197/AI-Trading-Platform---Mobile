from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.analysis_pipeline import UnifiedAnalysisPipeline
from app.ai_decision_engine import AIDecisionEngine
from app.market_context import Candle
from app.setup_risk_engine import RiskConfig, SetupRiskEngine


@dataclass(frozen=True)
class UnifiedBacktestConfig:
    initial_equity: float = 100_000.0
    risk_fraction: float = 0.01
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0001
    min_reward_risk: float = 2.0
    warmup_bars: int = 30


@dataclass(frozen=True)
class UnifiedBacktestTrade:
    entry_time: object
    exit_time: object
    side: str
    entry: float
    exit: float
    quantity: float
    net_pnl: float
    reason: str


@dataclass
class UnifiedBacktestResult:
    initial_equity: float
    final_equity: float
    trades: list[UnifiedBacktestTrade] = field(default_factory=list)

    @property
    def net_pnl(self) -> float:
        return self.final_equity - self.initial_equity

    @property
    def win_rate(self) -> float:
        return sum(t.net_pnl > 0 for t in self.trades) / len(self.trades) if self.trades else 0.0


class UnifiedBacktestEngine:
    """Uses the same MarketContext, AI decision and risk-sizing logic for historical simulation."""

    def __init__(self, pipeline=None, decision_engine=None, config=None):
        self.pipeline = pipeline or UnifiedAnalysisPipeline()
        self.decision_engine = decision_engine or AIDecisionEngine()
        self.config = config or UnifiedBacktestConfig()
        self.risk_engine = SetupRiskEngine(RiskConfig(
            min_reward_risk=self.config.min_reward_risk,
            risk_fraction=self.config.risk_fraction,
        ))

    def run(self, symbol: str, timeframe: str, candles: Sequence[Candle]) -> UnifiedBacktestResult:
        if self.config.initial_equity <= 0 or self.config.warmup_bars < 20:
            raise ValueError("invalid backtest configuration")
        if len(candles) <= self.config.warmup_bars:
            raise ValueError("insufficient candles for warmup")

        equity = self.config.initial_equity
        trades: list[UnifiedBacktestTrade] = []

        for i in range(self.config.warmup_bars, len(candles) - 1):
            history = candles[:i + 1]
            context = self.pipeline.build(symbol, timeframe, history)
            decision = self.decision_engine.decide(context)
            setup = self.risk_engine.validate(decision, equity)
            if setup is None or not setup.approved:
                continue

            bar = candles[i + 1]
            direction = 1 if setup.side == "BUY" else -1
            entry = setup.entry * (1 + direction * self.config.slippage_rate)
            stop_hit = bar.low <= setup.stop_loss if direction == 1 else bar.high >= setup.stop_loss
            target_hit = bar.high >= setup.target if direction == 1 else bar.low <= setup.target
            if not stop_hit and not target_hit:
                continue

            # Conservative intrabar assumption: if both levels are touched, stop wins.
            if stop_hit:
                exit_price = setup.stop_loss
                reason = "STOP_LOSS"
            else:
                exit_price = setup.target
                reason = "TAKE_PROFIT"
            exit_price *= 1 - direction * self.config.slippage_rate
            gross = (exit_price - entry) * setup.quantity * direction
            costs = (abs(entry * setup.quantity) + abs(exit_price * setup.quantity)) * self.config.commission_rate
            net = gross - costs
            equity += net
            trades.append(UnifiedBacktestTrade(
                entry_time=candles[i].timestamp,
                exit_time=bar.timestamp,
                side=setup.side,
                entry=entry,
                exit=exit_price,
                quantity=setup.quantity,
                net_pnl=net,
                reason=reason,
            ))

        return UnifiedBacktestResult(self.config.initial_equity, equity, trades)
