from dataclasses import dataclass, asdict
import pandas as pd

@dataclass
class BacktestResult:
    starting_balance: float
    ending_balance: float
    net_profit: float
    trades: int
    wins: int
    losses: int
    win_rate: float
    max_drawdown: float


def run(df: pd.DataFrame, starting_balance: float = 100000, risk_fraction: float = 0.005) -> dict:
    balance = starting_balance
    peak = balance
    max_dd = 0.0
    trades=wins=losses=0
    for i in range(3, len(df)):
        prev = df.iloc[i-1]; cur=df.iloc[i]
        if float(prev.close) > float(prev.open) and float(cur.close) > float(cur.open):
            entry=float(cur.open); stop=float(cur.low); target=entry + 2*(entry-stop)
            if target <= entry: continue
            risk=balance*risk_fraction
            if float(cur.high) >= target:
                balance += risk*2; wins += 1
            elif float(cur.low) <= stop:
                balance -= risk; losses += 1
            else:
                continue
            trades += 1
            peak=max(peak,balance); max_dd=max(max_dd,(peak-balance)/peak if peak else 0)
    result=BacktestResult(starting_balance,balance,balance-starting_balance,trades,wins,losses,(wins/trades*100 if trades else 0),max_dd*100)
    return asdict(result)
