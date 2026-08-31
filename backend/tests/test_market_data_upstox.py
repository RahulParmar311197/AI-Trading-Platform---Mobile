from app.market_data import Instrument
from app.market_data.upstox import UpstoxMarketDataNormalizer


RELIANCE = Instrument(symbol="RELIANCE", exchange="NSE", instrument_token="NSE_EQ|123")


def test_normalizes_upstox_v3_ltpc_feed():
    normalizer = UpstoxMarketDataNormalizer({"NSE_EQ|123": RELIANCE})
    ticks = normalizer.normalize({
        "type": "live_feed",
        "feeds": {
            "NSE_EQ|123": {
                "ltpc": {"ltp": 2501.5, "ltt": "1756602900000", "ltq": "25"}
            }
        },
        "currentTs": "1756602900100",
    })
    assert len(ticks) == 1
    assert ticks[0].instrument == RELIANCE
    assert ticks[0].price == 2501.5
    assert ticks[0].volume == 25


def test_normalizes_full_feed_nested_ltpc():
    normalizer = UpstoxMarketDataNormalizer({"NSE_EQ|123": RELIANCE})
    ticks = normalizer.normalize({
        "type": "live_feed",
        "feeds": {
            "NSE_EQ|123": {
                "fullFeed": {
                    "marketFF": {
                        "ltpc": {"ltp": 2502, "ltt": "1756602900000", "ltq": "5"}
                    }
                }
            }
        },
    })
    assert len(ticks) == 1
    assert ticks[0].price == 2502


def test_ignores_unknown_instruments_and_non_live_messages():
    normalizer = UpstoxMarketDataNormalizer({"NSE_EQ|123": RELIANCE})
    assert normalizer.normalize({"type": "market_info", "feeds": {}}) == []
    assert normalizer.normalize({
        "type": "live_feed",
        "feeds": {"NSE_EQ|999": {"ltpc": {"ltp": 100, "ltt": "1756602900000"}}},
    }) == []
