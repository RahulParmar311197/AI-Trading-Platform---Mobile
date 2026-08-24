import pytest
from app.ai_trading_journal import AITradingJournal


def test_win_loss_outcome():
    journal = AITradingJournal()
    win = journal.create_entry({"trade_id":"T1","decision":"APPROVED","expected":{},"actual":{"pnl":100}})
    loss = journal.create_entry({"trade_id":"T2","decision":"APPROVED","expected":{},"actual":{"pnl":-50}})
    assert win.outcome == "WIN"
    assert loss.outcome == "LOSS"


def test_rejected_outcome_is_preserved():
    entry = AITradingJournal().create_entry({"trade_id":"T3","decision":"REJECTED","expected":{},"actual":{"status":"REJECTED"}})
    assert entry.outcome == "REJECTED"


def test_required_fields():
    with pytest.raises(ValueError):
        AITradingJournal().create_entry({"trade_id":"T4"})
