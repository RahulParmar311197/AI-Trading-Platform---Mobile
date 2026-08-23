from __future__ import annotations
from dataclasses import dataclass
from app.mtf_ensemble import decide_mtf
from app.market_data import Candle
from app.ml_metrics import trading_metrics

@dataclass
class UnifiedBacktestConfig:
    initial_capital: float = 100000.0
    risk_per_trade: float = 0.01
    fee_bps: float = 3.0
    slippage_bps: float = 1.0
    stop_distance_pct: float = 0.003
    target_distance_pct: float = 0.006
    min_confidence: float = 0.35


def run(candles_by_tf: dict[str, list[Candle]], execution_tf: str, cfg: UnifiedBacktestConfig) -> dict:
    execution = candles_by_tf.get(execution_tf, [])
    if len(execution) < 30: raise ValueError("execution timeframe needs at least 30 candles")
    capital = cfg.initial_capital; curve=[capital]; returns=[]; trades=[]; position=None
    for i in range(30, len(execution)):
        c=execution[i]
        if position:
            d=position["direction"]
            stop_hit=c.low <= position["stop"] if d==1 else c.high >= position["stop"]
            target_hit=c.high >= position["target"] if d==1 else c.low <= position["target"]
            if stop_hit or target_hit:
                px=position["stop"] if stop_hit else position["target"]
                pnl=(px-position["entry"])*position["qty"]*d
                costs=(position["entry"]*position["qty"]+px*position["qty"])*(cfg.fee_bps+cfg.slippage_bps)/10000
                pnl-=costs; returns.append(pnl/capital); capital+=pnl; curve.append(capital)
                trades.append({"entry":position["entry"],"exit":px,"direction":d,"pnl":pnl,"reason":"STOP" if stop_hit else "TARGET"}); position=None
            continue
        frames={tf: cs[:i+1] for tf,cs in candles_by_tf.items() if len(cs)>i}
        decision=decide_mtf(frames)
        if decision["action"]=="NO_TRADE" or decision["confidence"]<cfg.min_confidence: continue
        d=1 if decision["action"]=="BUY" else -1; entry=c.close*(1+d*cfg.slippage_bps/10000)
        stop=entry*(1-d*cfg.stop_distance_pct); target=entry*(1+d*cfg.target_distance_pct)
        distance=abs(entry-stop); qty=(capital*cfg.risk_per_trade)/distance
        position={"entry":entry,"stop":stop,"target":target,"qty":qty,"direction":d,"confidence":decision["confidence"]}
    return {"config":cfg.__dict__,"metrics":trading_metrics(returns),"trades":trades,"equity_curve":curve,"open_position":position}
