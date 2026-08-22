from __future__ import annotations
import sqlite3
from datetime import datetime,timezone
from pathlib import Path
from app.mtf_aggregator import Candle

def _utc(dt:datetime)->datetime:
    if dt.tzinfo is None:return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
def _ts(dt:datetime)->str:return _utc(dt).isoformat()
class HistoricalMarketStore:
    def __init__(self,db_path:str="data/market_data.sqlite3"):
        self.db_path=db_path; Path(db_path).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(db_path,timeout=30) as db:
            db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA busy_timeout=30000")
            db.execute("CREATE TABLE IF NOT EXISTS candles (symbol TEXT NOT NULL,timeframe TEXT NOT NULL,timestamp TEXT NOT NULL,open REAL NOT NULL,high REAL NOT NULL,low REAL NOT NULL,close REAL NOT NULL,volume REAL NOT NULL,PRIMARY KEY(symbol,timeframe,timestamp))")
            db.execute("CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(symbol,timeframe,timestamp)")
    def upsert(self,candles:list[Candle]):
        if not candles:return 0
        rows=[(c.symbol.upper(),c.timeframe,_ts(c.timestamp),c.open,c.high,c.low,c.close,c.volume) for c in candles]
        with sqlite3.connect(self.db_path,timeout=30) as db:
            db.execute("PRAGMA busy_timeout=30000")
            db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(symbol,timeframe,timestamp) DO UPDATE SET open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,volume=excluded.volume",rows)
        return len(rows)
    def query(self,symbol:str,timeframe:str,start:datetime|None=None,end:datetime|None=None,limit:int=5000):
        sql="SELECT symbol,timeframe,timestamp,open,high,low,close,volume FROM candles WHERE symbol=? AND timeframe=?"; args=[symbol.upper(),timeframe]
        if start:sql+=" AND timestamp>=?";args.append(_ts(start))
        if end:sql+=" AND timestamp<=?";args.append(_ts(end))
        sql+=" ORDER BY timestamp ASC LIMIT ?";args.append(max(1,min(limit,100000)))
        with sqlite3.connect(self.db_path,timeout=30) as db:
            db.execute("PRAGMA busy_timeout=30000");rows=db.execute(sql,args).fetchall()
        return [dict(zip(("symbol","timeframe","timestamp","open","high","low","close","volume"),r)) for r in rows]
    def count(self,symbol:str,timeframe:str):
        with sqlite3.connect(self.db_path,timeout=30) as db:return db.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe=?",(symbol.upper(),timeframe)).fetchone()[0]
