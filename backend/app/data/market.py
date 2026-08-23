from dataclasses import dataclass
from datetime import datetime, timezone
import random

@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    timestamp: str

class MarketDataProvider:
    def quote(self, symbol: str, last_price: float = 100.0) -> Quote:
        price = max(0.01, last_price * (1 + random.uniform(-0.001, 0.001)))
        return Quote(symbol, round(price, 4), datetime.now(timezone.utc).isoformat())

market_data = MarketDataProvider()
