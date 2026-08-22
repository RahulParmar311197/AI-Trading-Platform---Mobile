from datetime import datetime,timezone,timedelta
from app.data_quality import CandleQualityValidator
from app.market_data import Candle

def c(t,o=100,h=102,l=99,cl=101,v=100):return Candle('NIFTY','15m',t,o,h,l,cl,v)
def test_invalid_ohlc_and_negative_volume():
 t=datetime(2026,1,1,tzinfo=timezone.utc); issues=CandleQualityValidator().validate([c(t,h=98),c(t+timedelta(minutes=15),v=-1)]); assert {x.code for x in issues}>={'INVALID_OHLC','NEGATIVE_VOLUME'}
def test_gap_and_duplicate():
 t=datetime(2026,1,1,tzinfo=timezone.utc); issues=CandleQualityValidator().validate([c(t),c(t),c(t+timedelta(hours=2))],timedelta(minutes=15)); assert any(x.code=='DUPLICATE_TIMESTAMP' for x in issues); assert any(x.code=='DATA_GAP' for x in issues)
def test_empty_data():assert CandleQualityValidator().validate([])[0].code=='EMPTY_DATA'
