from app.broker_adapter import BrokerOrder, PaperBrokerAdapter


def test_paper_adapter_submits_and_cancels():
    broker=PaperBrokerAdapter()
    result=broker.submit_order(BrokerOrder('NIFTY','BUY',10))
    assert result['status']=='FILLED'
    oid=result['broker_order_id']
    cancelled=broker.cancel_order(oid)
    assert cancelled['status']=='CANCELLED'


def test_paper_adapter_rejects_invalid_quantity():
    broker=PaperBrokerAdapter()
    try:
        broker.submit_order(BrokerOrder('NIFTY','BUY',0))
        assert False
    except ValueError:
        pass


def test_paper_adapter_exposes_account_and_positions():
    broker=PaperBrokerAdapter()
    assert broker.get_account()['mode']=='paper'
    assert broker.get_positions()==[]


def test_client_order_lookup_fails_closed_when_capability_is_missing():
    class NoOrderListBroker(PaperBrokerAdapter):
        get_orders = None

    broker = NoOrderListBroker()
    try:
        broker.find_order_by_client_id('missing')
        assert False
    except NotImplementedError as exc:
        assert 'client-order reconciliation' in str(exc)


def test_client_order_lookup_returns_exact_match():
    class OrderListBroker(PaperBrokerAdapter):
        def get_orders(self):
            return [
                {'order_id': 'b1', 'client_order_id': 'c1', 'status': 'FILLED'},
                {'order_id': 'b2', 'client_order_id': 'c2', 'status': 'NEW'},
            ]

    assert OrderListBroker().find_order_by_client_id('c1')['order_id'] == 'b1'


def test_client_order_lookup_returns_none_for_confirmed_absence():
    class OrderListBroker(PaperBrokerAdapter):
        def get_orders(self):
            return [{'order_id': 'b1', 'client_order_id': 'c1', 'status': 'FILLED'}]

    assert OrderListBroker().find_order_by_client_id('missing') is None


def test_client_order_lookup_fails_closed_on_duplicate_identity():
    class OrderListBroker(PaperBrokerAdapter):
        def get_orders(self):
            return [
                {'order_id': 'b1', 'client_order_id': 'c1', 'status': 'FILLED'},
                {'order_id': 'b2', 'client_order_id': 'c1', 'status': 'NEW'},
            ]

    try:
        OrderListBroker().find_order_by_client_id('c1')
        assert False
    except RuntimeError as exc:
        assert 'ambiguous broker order identity' in str(exc)
