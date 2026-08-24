import pandas as pd
from app.ict_engine import structure
from app.smc.engine import analyze


def candles(n=40):
    rows=[]
    for i in range(n):
        base=100+i*0.2
        rows.append({'timestamp':f'2026-01-01T00:{i:02d}:00Z','open':base,'high':base+1,'low':base-1,'close':base+0.5,'volume':1000+i})
    return rows


def test_ict_evidence_has_explicit_schema():
    result=structure(candles())
    assert result['status'] == 'ok'
    assert 'fvg' in result
    assert 'liquidity_pools' in result
    assert 'liquidity_sweeps' in result
    assert 'order_blocks' in result


def test_smc_and_ict_accept_same_ohlcv_frame():
    frame=pd.DataFrame(candles())
    smc=analyze(frame)
    ict=structure(candles())
    assert isinstance(smc, dict)
    assert isinstance(ict, dict)
    assert ict['status'] == 'ok'
