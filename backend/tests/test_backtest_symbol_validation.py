from datetime import datetime, timezone
from pathlib import Path
from app.backtest_service import BacktestService
from app.symbol_config import load_symbol_registry

def test_catalog_contains_expected_exchange_pairs():
    root=Path(__file__).resolve().parents[1]
    registry=load_symbol_registry(root/'config'/'symbols.json')
    assert registry.validate('NIFTY','NSE').exchange == 'NSE'
    assert registry.validate('SENSEX','BSE').exchange == 'BSE'

def test_wrong_exchange_is_rejected_before_data_fetch(tmp_path):
    catalog=tmp_path/'symbols.json'
    catalog.write_text('[{"symbol":"NIFTY","exchange":"NSE"}]',encoding='utf-8')
    service=BacktestService(str(tmp_path),symbol_catalog=str(catalog))
    try:
        service.run('NIFTY','15m',datetime(2026,1,1,tzinfo=timezone.utc),datetime(2026,1,2,tzinfo=timezone.utc),100000,1,'BSE')
        assert False
    except ValueError as exc:
        assert 'not registered' in str(exc)
