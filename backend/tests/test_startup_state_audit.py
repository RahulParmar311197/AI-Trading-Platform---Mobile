import json

from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine
from app.trading_audit import TradingAuditLog


def test_all_state_transitions_are_audited(tmp_path):
    audit = TradingAuditLog(str(tmp_path / 'audit.jsonl'))
    state = StartupExecutionStateMachine(audit)
    state.transition(StartupExecutionState.RECOVERING)
    state.transition(StartupExecutionState.BROKER_RECONCILED)
    state.transition(StartupExecutionState.PORTFOLIO_RECONCILED)
    state.transition(StartupExecutionState.RISK_READY)
    state.transition(StartupExecutionState.READY)

    rows = [json.loads(line) for line in (tmp_path / 'audit.jsonl').read_text().splitlines()]
    assert [row['to_state'] for row in rows] == [
        'RECOVERING', 'BROKER_RECONCILED', 'PORTFOLIO_RECONCILED', 'RISK_READY', 'READY'
    ]
