from __future__ import annotations
from dataclasses import dataclass
from statistics import mean, pstdev
from app.strategy import generate_signal
from app.market_data import Candle
from app.position_sizing import size_position
from app.order_intent import OrderIntent
from app.risk_gateway import authorize
from app.risk_engine import RiskLimits
from app.execution import PaperBroker, execute_paper
from app.portfolio import PaperPortfolio

@dataclass
class BacktestTrade:
    side: str
    entry: float
    exit: float
    pnl: float
    bars: int
    reason: str


def run_backtest(candles: list[Candle], starting_equity: float = 100000.0, risk_percent: float = 1.0, fee_bps: float = 3.0, slippage_bps: float = 1.0, limits: RiskLimits | None = None) -> dict:
    if starting_equity <= 0 or risk_percent <= 0 or risk_percent > 5 or len(candles) < 25:
        raise ValueError('invalid capital/risk or insufficient candles')
    if fee_bps < 0 or slippage_bps < 0:
        raise ValueError('cost parameters cannot be negative')
    portfolio = PaperPortfolio(starting_equity)
    broker = PaperBroker()
    peak = starting_equity
    max_dd = 0.0
    trades: list[BacktestTrade] = []
    returns: list[float] = []
    equity_curve = [starting_equity]
    i = 20
    skipped_risk = 0
    while i < len(candles) - 1:
        signal = generate_signal(candles[:i + 1])
        if signal is None:
            i += 1
            continue
        entry_bar = i + 1
        direction = 1 if signal.action == 'BUY' else -1
        raw_entry = candles[entry_bar].open
        entry = raw_entry * (1 + direction * slippage_bps / 10000)
        if (direction == 1 and not signal.stop_loss < entry < signal.target) or (direction == -1 and signal.target < entry < signal.stop_loss):
            i += 1
            continue
        sizing = size_position(portfolio.equity, risk_percent, entry, signal.stop_loss)
        order = OrderIntent(candles[entry_bar].symbol, signal.action, entry, signal.stop_loss, signal.target, sizing['quantity'], sizing['risk_amount'], 'backtest', signal.confidence)
        risk = authorize(order=order, equity=portfolio.equity, daily_pnl=portfolio.realized_pnl, open_positions=len(portfolio.positions), limits=limits)
        if not risk.approved:
            skipped_risk += 1
            i += 1
            continue
        fill = execute_paper(risk=risk, broker=broker)
        portfolio.apply_fill(order, fill)
        exit_price = candles[-1].close
        reason = 'END_OF_TEST'
        exit_i = len(candles) - 1
        for j in range(entry_bar, len(candles)):
            bar = candles[j]
            stop_hit = bar.low <= signal.stop_loss if direction == 1 else bar.high >= signal.stop_loss
            target_hit = bar.high >= signal.target if direction == 1 else bar.low <= signal.target
            if stop_hit or target_hit:
                # Conservative rule when both levels are touched in one candle: stop wins.
                if stop_hit:
                    exit_price = signal.stop_loss
                    reason = 'STOP_LOSS'
                else:
                    exit_price = signal.target
                    reason = 'TAKE_PROFIT'
                exit_i = j
                break
            exit_price = bar.close
            exit_i = j
        exit_price *= 1 - direction * slippage_bps / 10000
        close = portfolio.close_position(order.symbol, exit_price, reason)
        costs = (entry * order.quantity + exit_price * order.quantity) * fee_bps / 10000
        portfolio.realized_pnl -= costs
        pnl = close.realized_pnl - costs
        prior_equity = portfolio.equity - pnl
        returns.append(pnl / max(prior_equity, 1e-9))
        equity_curve.append(portfolio.equity)
        peak = max(peak, portfolio.equity)
        max_dd = max(max_dd, (peak - portfolio.equity) / peak if peak else 0)
        trades.append(BacktestTrade(signal.action, entry, exit_price, pnl, exit_i - entry_bar + 1, reason))
        i = max(i + 1, exit_i + 1)

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    avg = mean(returns) if returns else 0.0
    sd = pstdev(returns) if len(returns) > 1 else 0.0
    ending = portfolio.equity
    return {
        'starting_equity': starting_equity,
        'ending_equity': ending,
        'net_pnl': ending - starting_equity,
        'return_percent': (ending / starting_equity - 1) * 100,
        'trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trades) if trades else 0,
        'profit_factor': gross_profit / gross_loss if gross_loss else None,
        'max_drawdown_percent': max_dd * 100,
        'sharpe': (avg / sd) * (len(returns) ** 0.5) if sd else 0,
        'risk_rejected': skipped_risk,
        'equity_curve': equity_curve,
        'trade_journal': [t.__dict__ for t in trades],
    }
