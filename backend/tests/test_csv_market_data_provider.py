import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.csv_market_data_provider import CsvMarketDataProvider


def test_csv_provider(tmp_path: Path):
    p = tmp_path / 'NIFTY_15m.csv'
    p.write_text(
        'timestamp,open,high,low,close,volume\n'
        '2026-01-01T09:15:00+00:00,100,102,99,101,1000\n'
        '2026-01-01T09:30:00+00:00,101,103,100,102,1100\n',
        encoding='utf-8',
    )
    s = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = asyncio.run(CsvMarketDataProvider(tmp_path).historical('NIFTY', '15m', s, s + timedelta(days=1)))
    assert len(rows) == 2
    assert rows[0].close == 101


def test_missing_file(tmp_path: Path):
    try:
        asyncio.run(CsvMarketDataProvider(tmp_path).historical('NIFTY', '15m', datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc)))
        assert False
    except FileNotFoundError:
        pass
