import pytest

from app.execution_persistence import ExecutionStateStore
from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle


def test_live_execution_service_requires_unified_startup_state(tmp_path):
    with pytest.raises(ValueError, match="startup_state is required"):
        OrderExecutionService(
            router=object(),
            lifecycle=OrderLifecycle(),
            store=ExecutionStateStore(str(tmp_path / "execution.json")),
        )
