import pytest

from app.broker_adapter import BrokerAdapter, BrokerOrderRequest, BrokerOrderUpdate
from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_order_snapshot import BrokerOrderSnapshot
from app.broker_position_snapshot import BrokerPositionSnapshot


class ResponseAdapter(BrokerAdapter):
    def __init__(self, response):
        self.response = response
        self.submissions = 0

    def submit_order(self, order):
        self.submissions += 1
        return self.response

    def cancel_order(self, broker_order_id):
        raise NotImplementedError

    def get_order(self, broker_order_id):
        raise NotImplementedError

    def get_positions(self):
        return []

    def get_account(self):
        return {"healthy": True}

    def get_order_snapshot(self):
        return BrokerOrderSnapshot(orders=[], complete=True, source="test")

    def get_position_snapshot(self):
        return BrokerPositionSnapshot(positions=[], complete=True, source="test")


REQUEST = BrokerOrderRequest(
    client_order_id="client-1",
    symbol="NIFTY",
    side="BUY",
    quantity=5,
    broker_account_id=101,
)


def router_for(response):
    adapter = ResponseAdapter(response)
    router = BrokerRouter([BrokerRoute("test", adapter)], "test")
    return router, adapter


def test_successful_submission_response_is_normalized_and_identity_bound():
    router, adapter = router_for(
        BrokerOrderUpdate(
            order_id="broker-1",
            status="NEW",
            client_order_id="client-1",
            symbol="NIFTY",
            side="BUY",
            quantity=5,
            broker_account_id=101,
        )
    )

    result = router.submit(REQUEST)

    assert result.order_id == "broker-1"
    assert result.client_order_id == "client-1"
    assert result.symbol == "NIFTY"
    assert result.side == "BUY"
    assert result.quantity == 5
    assert result.broker_account_id == 101
    assert adapter.submissions == 1
    assert router.unresolved_submission_intent_count() == 0


def test_missing_submit_response_identity_fails_closed_and_leaves_intent_unresolved():
    router, adapter = router_for(
        BrokerOrderUpdate(order_id="broker-1", status="NEW", quantity=5)
    )

    with pytest.raises(ValueError, match="broker client_order_id does not match request"):
        router.submit(REQUEST)

    assert adapter.submissions == 1
    assert router.unresolved_submission_intent_count() == 1


def test_submit_response_quantity_mismatch_fails_closed_and_leaves_intent_unresolved():
    router, adapter = router_for(
        BrokerOrderUpdate(
            order_id="broker-1",
            status="NEW",
            client_order_id="client-1",
            symbol="NIFTY",
            side="BUY",
            quantity=4,
            broker_account_id=101,
        )
    )

    with pytest.raises(ValueError, match="broker quantity does not match requested quantity"):
        router.submit(REQUEST)

    assert adapter.submissions == 1
    assert router.unresolved_submission_intent_count() == 1


def test_submit_response_account_mismatch_fails_closed_and_leaves_intent_unresolved():
    router, adapter = router_for(
        BrokerOrderUpdate(
            order_id="broker-1",
            status="NEW",
            client_order_id="client-1",
            symbol="NIFTY",
            side="BUY",
            quantity=5,
            broker_account_id=202,
        )
    )

    with pytest.raises(ValueError, match="broker account does not match request"):
        router.submit(REQUEST)

    assert adapter.submissions == 1
    assert router.unresolved_submission_intent_count() == 1


def test_malformed_broker_account_identity_fails_closed():
    with pytest.raises(ValueError, match="invalid broker account identity"):
        from app.broker_adapter import normalize_broker_update

        normalize_broker_update(
            {
                "order_id": "broker-1",
                "status": "NEW",
                "client_order_id": "client-1",
                "symbol": "NIFTY",
                "side": "BUY",
                "quantity": 5,
                "broker_account_id": "not-an-account",
            },
            expected=REQUEST,
        )
