from __future__ import annotations
from dataclasses import dataclass
from app.execution import ExecutionResult
from app.order_intent import OrderIntent
from app.trailing_stop import TrailingPolicy, update_stop

@dataclass
class Position:
    symbol: str; side: str; quantity: float; entry_price: float; stop_loss: float; take_profit: float
    initial_stop: float | None = None; entry_cost: float = 0.0; realized_pnl: float = 0.0; partial_taken: bool = False
    def __post_init__(self):
        if self.initial_stop is None: self.initial_stop=self.stop_loss
    def unrealized_pnl(self, mark_price: float, quantity: float | None = None) -> float:
        q=self.quantity if quantity is None else quantity; direction=1.0 if self.side=='BUY' else -1.0
        return (mark_price-self.entry_price)*q*direction

@dataclass(frozen=True)
class CloseResult:
    symbol: str; side: str; entry_price: float; exit_price: float; quantity: float; realized_pnl: float; reason: str
    commission: float=0.0; slippage: float=0.0

class PaperPortfolio:
    def __init__(self, initial_equity: float):
        if initial_equity<=0: raise ValueError('initial_equity must be positive')
        self.initial_equity=initial_equity; self.realized_pnl=0.0; self.positions: dict[str,Position]={}; self.total_commission=0.0; self.total_slippage=0.0
    @property
    def equity(self): return self.initial_equity+self.realized_pnl-self.total_commission
    @property
    def exposure(self): return sum(abs(p.entry_price*p.quantity) for p in self.positions.values())
    def apply_fill(self, order: OrderIntent, fill: ExecutionResult) -> Position:
        if fill.filled_quantity<=0: raise ValueError('fill quantity must be positive')
        self.total_commission += fill.commission; self.total_slippage += fill.slippage
        pos=Position(order.symbol,order.side,fill.filled_quantity,fill.fill_price,order.stop_loss,order.take_profit,order.stop_loss,fill.commission)
        self.positions[order.symbol]=pos; return pos
    def update_trailing(self, prices: dict[str,float], policy: TrailingPolicy|None=None) -> None:
        for symbol,p in self.positions.items():
            if symbol in prices: p.stop_loss=update_stop(p.side,p.entry_price,p.initial_stop,prices[symbol],p.stop_loss,policy)
    def close_position(self,symbol:str,exit_price:float,reason:str='MANUAL',quantity:float|None=None,commission:float=0.0,slippage:float=0.0)->CloseResult:
        if symbol not in self.positions: raise KeyError(f'no open position: {symbol}')
        p=self.positions[symbol]; q=p.quantity if quantity is None else quantity
        if exit_price<=0 or q<=0 or q>p.quantity: raise ValueError('invalid close')
        pnl=p.unrealized_pnl(exit_price,q)-commission; p.quantity-=q; p.realized_pnl+=pnl; self.realized_pnl+=pnl
        self.total_commission+=commission; self.total_slippage+=slippage
        if p.quantity==0: self.positions.pop(symbol)
        return CloseResult(symbol,p.side,p.entry_price,exit_price,q,pnl,reason,commission,slippage)
    def partial_close(self,symbol:str,exit_price:float,quantity:float,move_stop_to_breakeven:bool=True,commission:float=0.0,slippage:float=0.0)->CloseResult:
        result=self.close_position(symbol,exit_price,'PARTIAL_TP',quantity,commission,slippage)
        if symbol in self.positions and move_stop_to_breakeven: self.positions[symbol].stop_loss=self.positions[symbol].entry_price
        if symbol in self.positions: self.positions[symbol].partial_taken=True
        return result
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
        return {'initial_equity':self.initial_equity,'realized_pnl':self.realized_pnl,'unrealized_pnl':unrealized,'equity':self.equity+unrealized,'exposure':self.exposure,'open_positions':len(self.positions),'total_commission':self.total_commission,'total_slippage':self.total_slippage}
