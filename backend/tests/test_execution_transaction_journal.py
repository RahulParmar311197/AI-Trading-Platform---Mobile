from app.execution_transaction_journal import ExecutionJournalEntry, ExecutionTransactionJournal


def test_duplicate_event_is_not_reapplied(tmp_path):
    journal = ExecutionTransactionJournal(str(tmp_path / "execution.db"))
    entry = ExecutionJournalEntry("evt-1", "ord-1", "FILLED", "NIFTY", 10.0, {"qty": 10})
    assert journal.apply(entry) is True
    assert journal.apply(entry) is False
    pending = journal.pending_outbox()
    assert len(pending) == 1
    assert pending[0]["event_id"] == "evt-1"
    journal.close()


def test_outbox_survives_restart(tmp_path):
    path = str(tmp_path / "execution.db")
    first = ExecutionTransactionJournal(path)
    first.apply(ExecutionJournalEntry("evt-2", "ord-2", "PARTIAL_FILL", "NIFTY", 4.0, {"qty": 4}))
    first.close()
    second = ExecutionTransactionJournal(path)
    assert len(second.pending_outbox()) == 1
    assert second.pending_outbox()[0]["event_id"] == "evt-2"
    second.close()
