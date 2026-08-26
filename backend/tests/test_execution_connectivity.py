from app.broker_connectivity import BrokerConnectivitySupervisor, ConnectivityState
from app.execution import OrderStatus, execute_paper
from app.order_intent import OrderIntent
from app.risk_gateway import RiskGatewayResult


def approved_risk():
    order = OrderIntent("NIFTY", "BUY", 100, 99, 102, 1, 1, "test")
    return RiskGatewayResult(True, order, "approved")


def test_paper_execution_without_connectivity_is_unchanged():
    result = execute_paper(risk=approved_risk())
    assert result.status is OrderStatus.FILLED


def test_disconnected_connectivity_blocks_execution():
    supervisor = BrokerConnectivitySupervisor()
    result = execute_paper(risk=approved_risk(), connectivity=supervisor)
    assert result.status is OrderStatus.REJECTED
    assert "connectivity" in result.message


def test_healthy_connectivity_allows_execution():
    supervisor = BrokerConnectivitySupervisor()
    supervisor.record_success()
    assert supervisor.snapshot().state is ConnectivityState.HEALTHY
    result = execute_paper(risk=approved_risk(), connectivity=supervisor)
    assert result.status is OrderStatus.FILLED


def test_risk_rejection_happens_before_connectivity():
    supervisor = BrokerConnectivitySupervisor()
    rejected = RiskGatewayResult(False, approved_risk().order, "risk rejected")
    result = execute_paper(risk=rejected, connectivity=supervisor)
    assert result.status is OrderStatus.REJECTED
    assert result.message == "risk gateway rejected order"
