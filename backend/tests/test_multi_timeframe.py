from datetime import datetime, timedelta
from app.market_data import Candle, market_data
from app.multi_timeframe import analyze, latest_context


def seed():
    base=datetime(2026,1,1)
    for tf in ['15m','1h','4h','1d']:
        for i in range(25):
            p=100+i*0.1
            market_data.put(Candle(base+timedelta(minutes=i), 'NIFTY', tf, p,p+1,p-1,p+0.5,100))


def test_mtf_analysis_and_context():
    seed(); result=analyze('NIFTY',['15m','1h','4h'])
    assert len(result['timeframes'])==3
    assert result['symbol']=='NIFTY'
    context=latest_context('NIFTY',['15m','1h','4h','1d'])
    assert all(context[k] is not None for k in context)


def test_unsupported_timeframe_rejected():
    try:
        analyze('NIFTY',['2h'])
        assert False
    except ValueError:
        pass
