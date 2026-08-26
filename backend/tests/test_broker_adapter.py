from app.broker_adapter import BrokerOrder, BrokerOrderRequest, PaperBrokerAdapter


def test_paper_adapter_submits_and_filled_order_cannot_be_cancelled():
    broker=PaperBrokerAdapter()
    result=broker.submit_order(BrokerOrder('NIFTY','BUY',10))
    assert result['status']=='FILLED'
    oid=result['broker_order_id']
    cancelled=broker.cancel_order(oid)
    assert cancelled['status']=='FILLED'


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


def test_paper_broker_client_id_submission_is_idempotent():
    broker=PaperBrokerAdapter()
    first=broker.submit_order(BrokerOrderRequest('c1','NIFTY','BUY',10))
    second=broker.submit_order(BrokerOrderRequest('c1','NIFTY','BUY',10))
    assert first['broker_order_id']==second['broker_order_id']
    assert len(broker.get_orders())==1
