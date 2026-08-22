from __future__ import annotations
from dataclasses import dataclass
from app.execution import ExecutionResult
from app.order_intent import OrderIntent
from app.trailing_stop import TrailingPolicy, update_stop

@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    initial_stop: float | None = None
    realized_pnl: float = 0.0
    def __post_init__(self):
        if self.initial_stop is None: self.initial_stop=self.stop_loss
    def unrealized_pnl(self, mark_price: float) -> float:
        direction=1.0 if self.side=='BUY' else -1.0
        return (mark_price-self.entry_price)*self.quantity*direction

@dataclass(frozen=True)
class CloseResult:
    symbol: str; side: str; entry_price: float; exit_price: float; quantity: float; realized_pnl: float; reason: str

class PaperPortfolio:
    def __init__(self, initial_equity: float):
        if initial_equity<=0: raise ValueError('initial_equity must be positive')
        self.initial_equity=initial_equity; self.realized_pnl=0.0; self.positions: dict[str,Position]={}
    @property
    def equity(self): return self.initial_equity+self.realized_pnl
    @property
    def exposure(self): return sum(abs(p.entry_price*p.quantity) for p in self.positions.values())
    def apply_fill(self, order: OrderIntent, fill: ExecutionResult) -> Position:
        if fill.filled_quantity<=0: raise ValueError('fill quantity must be positive')
        pos=Position(order.symbol,order.side,fill.filled_quantity,fill.fill_price,order.stop_loss,order.take_profit,order.stop_loss); self.positions[order.symbol]=pos; return pos
    def update_trailing(self, prices: dict[str,float], policy: TrailingPolicy|None=None) -> None:
        for symbol,p in self.positions.items():
            if symbol in prices:
                p.stop_loss=update_stop(p.side,p.entry_price,p.initial_stop,prices[symbol],p.stop_loss,policy)
    def close_position(self,symbol:str,exit_price:float,reason:str='MANUAL')->CloseResult:
        if symbol not in self.positions: raise KeyError(f'no open position: {symbol}')
        if exit_price<=0: raise ValueError('exit_price must be positive')
        p=self.positions.pop(symbol); pnl=p.unrealized_pnl(exit_price); self.realized_pnl+=pnl
        return CloseResult(symbol,p.side,p.entry_price,exit_price,p.quantity,pnl,reason)
    def process_ohlc_bar(self,bars:dict[str,object])->list[CloseResult]:
        closed=[]
        for symbol,p in list(self.positions.items()):
            bar=bars.get(symbol)
            if bar is None: continue
            high=float(bar.high); low=float(bar.low); reason=None; exit_price=None
            if p.side=='BUY':
                if low<=p.stop_loss: reason='STOP_LOSS'; exit_price=p.stop_loss
                elif high>=p.take_profit: reason='TAKE_PROFIT'; exit_price=p.take_profit
            else:
                if high>=p.stop_loss: reason='STOP_LOSS'; exit_price=p.stop_loss
                elif low<=p.take_profit: reason='TAKE_PROFIT'; exit_price=p.take_profit
            if reason: closed.append(self.close_position(symbol,exit_price,reason))
        return closed
    def process_bar(self,prices:dict[str,float])->list[CloseResult]:
        closed=[]
        for symbol,p in list(self.positions.items()):
            if symbol not in prices: continue
            px=prices[symbol]; reason=None
            if p.side=='BUY':
                if px<=p.stop_loss: reason='STOP_LOSS'
                elif px>=p.take_profit: reason='TAKE_PROFIT'
            else:
                if px>=p.stop_loss: reason='STOP_LOSS'
                elif px<=p.take_profit: reason='TAKE_PROFIT'
            if reason: closed.append(self.close_position(symbol,px,reason))
        return closed
    def mark(self,prices:dict[str,float])->dict:
        unrealized=sum(p.unrealized_pnl(prices[p.symbol]) for p in self.positions.values() if p.symbol in prices)
        return {'initial_equity':self.initial_equity,'realized_pnl':self.realized_pnl,'unrealized_pnl':unrealized,'equity':self.equity+unrealized,'exposure':self.exposure,'open_positions':len(self.positions)}
