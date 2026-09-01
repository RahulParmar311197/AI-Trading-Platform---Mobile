from __future__ import annotations

from dataclasses import dataclass

from app.accounting import EquitySnapshot, calculate_equity
from app.strategy import generate_signal
from app.market_data import Candle
from app.position_sizing import size_position
from app.order_intent import OrderIntent
from app.risk_gateway import authorize
from app.risk_engine import RiskLimits
from app.execution import PaperBroker, execute_paper
from app.portfolio import PaperPortfolio
from app.ml_decision import MLDecisionConfig, apply_ml_decision
from app.performance_metrics import calculate_performance_metrics


@dataclass
class BacktestTrade:
    side: str
    entry: float
    exit: float
    pnl: float
    bars: int
    reason: str


def _canonical_candle(candle: Candle):
    from app.market_context import Candle as ContextCandle
    return ContextCandle(
        timestamp=candle.timestamp,
        open=float(candle.open), high=float(candle.high), low=float(candle.low),
        close=float(candle.close), volume=float(candle.volume),
    )


def _equity_snapshot(portfolio: PaperPortfolio, mark_price: float | None = None) -> float:
    unrealized = 0.0
    if mark_price is not None:
        prices = {symbol: mark_price for symbol in portfolio.positions}
        unrealized = sum(
            position.unrealized_pnl(prices[position.symbol])
            for position in portfolio.positions.values()
        )
    snapshot = EquitySnapshot(
        starting_equity=portfolio.initial_equity,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=unrealized,
        fees=portfolio.entry_commission,
        charges=0.0,
    )
    return calculate_equity(
        starting_equity=snapshot.starting_equity,
        realized_pnl=snapshot.realized_pnl,
        unrealized_pnl=snapshot.unrealized_pnl,
        fees=snapshot.fees,
        charges=snapshot.charges,
    )


def run_backtest(
    candles: list[Candle],
    starting_equity: float = 100000.0,
    risk_percent: float = 1.0,
    fee_bps: float = 3.0,
    slippage_bps: float = 1.0,
    limits: RiskLimits | None = None,
    *,
    enable_ml: bool = False,
    ml_predictor=None,
    ml_artifact=None,
    ml_confidence: float = 0.0,
    ml_config: MLDecisionConfig | None = None,
    ml_expected_features: tuple[str, ...] = (),
    ml_horizon: int = 5,
    ml_threshold: float = 0.002,
    strategy_mode: str = 'legacy',
    ai_symbol: str | None = None,
    ai_timeframe: str | None = None,
) -> dict:
    """Run the deterministic simulator with canonical accounting and metrics."""
    if starting_equity <= 0 or risk_percent <= 0 or risk_percent > 5 or len(candles) < 25:
        raise ValueError('invalid capital/risk or insufficient candles')
    if fee_bps < 0 or slippage_bps < 0:
        raise ValueError('cost parameters cannot be negative')
    if strategy_mode not in {'legacy', 'ai'}:
        raise ValueError('strategy_mode must be legacy or ai')
    ai_strategy = None
    if strategy_mode == 'ai':
        if not ai_symbol or not ai_timeframe:
            raise ValueError('ai_symbol and ai_timeframe are required for strategy_mode=ai')
        from app.ai_backtest_strategy import CanonicalAIBacktestStrategy
        ai_strategy = CanonicalAIBacktestStrategy(symbol=ai_symbol, timeframe=ai_timeframe)
    if enable_ml and (ml_predictor is None or ml_artifact is None):
        raise ValueError('ML predictor and artifact are required when enable_ml=True')

    portfolio = PaperPortfolio(starting_equity)
    broker = PaperBroker()
    trades: list[BacktestTrade] = []
    equity_curve = [starting_equity]
    i = 20
    skipped_risk = 0
    ml_rejected = 0

    while i < len(candles) - 1:
        history = candles[:i + 1]
        if strategy_mode == 'ai':
            if i < 49:
                i += 1
                continue
            context_history = tuple(_canonical_candle(c) for c in history)
            ai_decision = ai_strategy.decision(i, context_history)
            if ai_decision.decision == 'HOLD':
                i += 1
                continue
            class _Signal:
                action = ai_decision.decision
                quantity = 1
                confidence = ai_decision.confidence
                stop_loss = ai_decision.stop_loss
                target = ai_decision.target
            signal = _Signal()
        else:
            signal = generate_signal(history)

        if signal is None:
            i += 1
            continue
        if enable_ml:
            from app.ml_features import build_feature_vector
            from app.ml_inference import predict_one
            features = build_feature_vector(history)
            if features is None:
                i += 1
                continue
            prediction = predict_one(ml_predictor, ml_artifact, features, ml_expected_features, ml_horizon, ml_threshold)
            signal = apply_ml_decision(signal, prediction, ml_confidence, ml_config)
            if signal is None:
                ml_rejected += 1
                i += 1
                continue

        entry_bar = i + 1
        direction = 1 if signal.action == 'BUY' else -1
        raw_entry = candles[entry_bar].open
        entry = raw_entry * (1 + direction * slippage_bps / 10000)
        if signal.stop_loss is None or signal.target is None:
            i += 1
            continue
        if (direction == 1 and not signal.stop_loss < entry < signal.target) or (direction == -1 and not signal.target < entry < signal.stop_loss):
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
                exit_price = signal.stop_loss if stop_hit else signal.target
                reason = 'STOP_LOSS' if stop_hit else 'TAKE_PROFIT'
                exit_i = j
                break
            exit_price = bar.close
            exit_i = j

        exit_price *= 1 - direction * slippage_bps / 10000
        close = portfolio.close_position(order.symbol, exit_price, reason)
        costs = (entry * order.quantity + exit_price * order.quantity) * fee_bps / 10000
        portfolio.realized_pnl -= costs
        pnl = close.realized_pnl - costs
        equity_curve.append(_equity_snapshot(portfolio))
        trades.append(BacktestTrade(signal.action, entry, exit_price, pnl, exit_i - entry_bar + 1, reason))
        i = max(i + 1, exit_i + 1)

    # Mark any remaining state at the final candle before producing the report.
    if portfolio.positions:
        equity_curve.append(_equity_snapshot(portfolio, candles[-1].close))

    trade_pnls = [trade.pnl for trade in trades]
    metrics = calculate_performance_metrics(
        equity_curve,
        trade_pnls,
        initial_equity=starting_equity,
    )
    ending = _equity_snapshot(portfolio)
    return {
        'starting_equity': starting_equity,
        'ending_equity': ending,
        'net_pnl': ending - starting_equity,
        'return_percent': metrics.total_return * 100,
        'trades': metrics.trade_count,
        'wins': metrics.winning_trades,
        'losses': metrics.losing_trades,
        'win_rate': metrics.win_rate,
        'profit_factor': metrics.profit_factor,
        'max_drawdown_percent': metrics.max_drawdown_pct * 100,
        'sharpe': metrics.sharpe_ratio,
        'sortino': metrics.sortino_ratio,
        'calmar': metrics.calmar_ratio,
        'volatility': metrics.volatility,
        'gross_profit': metrics.gross_profit,
        'gross_loss': metrics.gross_loss,
        'risk_rejected': skipped_risk,
        'ml_rejected': ml_rejected,
        'equity_curve': equity_curve,
        'trade_journal': [t.__dict__ for t in trades],
        'strategy_mode': strategy_mode,
    }
