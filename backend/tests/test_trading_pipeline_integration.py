from dataclasses import dataclass

@dataclass
class Candle:
    close: float
    volume: float

@dataclass
class Signal:
    symbol: str
    side: str
    confidence: float
    quantity: int

class FakeRisk:
    def __init__(self, allowed=True): self.allowed = allowed
    def approve(self, signal): return self.allowed

class FakeExecution:
    def __init__(self): self.submitted = []
    def submit(self, signal):
        self.submitted.append(signal)
        return {"status": "accepted", "client_order_id": f"integration-{len(self.submitted)}"}

def generate_signal(candles):
    if len(candles) < 2 or candles[-1].close <= candles[-2].close:
        return None
    return Signal("NIFTY", "BUY", 0.80, 1)

def run_pipeline(candles, risk, execution):
    signal = generate_signal(candles)
    if signal is None or not risk.approve(signal):
        return {"status": "blocked", "signal": signal}
    return execution.submit(signal)

def test_market_data_to_execution_pipeline():
    execution = FakeExecution()
    result = run_pipeline([Candle(100, 1000), Candle(101, 1200)], FakeRisk(), execution)
    assert result["status"] == "accepted"
    assert len(execution.submitted) == 1
    assert execution.submitted[0].symbol == "NIFTY"

def test_pipeline_stops_when_signal_is_invalid():
    execution = FakeExecution()
    result = run_pipeline([Candle(101, 1000), Candle(100, 1200)], FakeRisk(), execution)
    assert result["status"] == "blocked"
    assert execution.submitted == []

def test_pipeline_stops_at_risk_gate():
    execution = FakeExecution()
    result = run_pipeline([Candle(100, 1000), Candle(101, 1200)], FakeRisk(False), execution)
    assert result["status"] == "blocked"
    assert execution.submitted == []
