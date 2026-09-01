import math

import pytest

from app.broker_adapter import BrokerOrder, BrokerOrderRequest, PaperBrokerAdapter, normalize_broker_update


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


def test_normalize_broker_update_rejects_inconsistent_filled_status():
    with pytest.raises(ValueError, match='FILLED broker status'):
        normalize_broker_update({
            'order_id': 'b1', 'status': 'FILLED', 'quantity': 10,
            'filled_quantity': 9, 'average_price': 100,
        })


def test_normalize_broker_update_rejects_new_with_fill():
    with pytest.raises(ValueError, match='NEW broker status'):
        normalize_broker_update({
            'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
            'filled_quantity': 1,
        })


def test_normalize_broker_update_rejects_non_finite_or_non_positive_prices():
    with pytest.raises(ValueError, match='invalid broker price'):
        normalize_broker_update({'order_id': 'b1', 'status': 'NEW', 'quantity': 10, 'price': math.nan})
    with pytest.raises(ValueError, match='broker price must be positive'):
        normalize_broker_update({'order_id': 'b1', 'status': 'NEW', 'quantity': 10, 'price': 0})


def test_normalize_broker_update_accepts_valid_partial_fill():
    result = normalize_broker_update({
        'order_id': 'b1', 'status': 'PARTIALLY_FILLED', 'quantity': 10,
        'filled_quantity': 4, 'average_price': 100,
    })
    assert result.status == 'PARTIALLY_FILLED'
    assert result.filled_quantity == 4


def test_normalize_broker_update_rejects_missing_account_identity_when_request_is_scoped():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
        broker_account_id='acct-42',
    )
    with pytest.raises(ValueError, match='missing account identity'):
        normalize_broker_update({
            'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
            'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
        }, expected=request)


def test_normalize_broker_update_accepts_matching_opaque_account_identity():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
        broker_account_id='001',
    )
    result = normalize_broker_update({
        'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
        'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
        'broker_account_id': '001',
    }, expected=request)
    assert result.broker_account_id == '001'


def test_normalize_broker_update_keeps_distinct_opaque_accounts_distinct():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
        broker_account_id='001',
    )
    with pytest.raises(ValueError, match='broker account does not match request'):
        normalize_broker_update({
            'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
            'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
            'broker_account_id': '1',
        }, expected=request)


def test_normalize_broker_update_rejects_missing_route_identity_when_request_is_scoped():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
        broker_account_id='acct-42', broker_route='upstox-primary',
        broker_route_generation='7',
    )
    with pytest.raises(ValueError, match='missing route identity'):
        normalize_broker_update({
            'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
            'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
            'broker_account_id': 'acct-42', 'broker_route_generation': '7',
        }, expected=request)


def test_normalize_broker_update_rejects_mismatched_route_identity():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
        broker_account_id='acct-42', broker_route='upstox-primary',
        broker_route_generation='7',
    )
    with pytest.raises(ValueError, match='broker route does not match request'):
        normalize_broker_update({
            'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
            'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
            'broker_account_id': 'acct-42', 'broker_route': 'upstox-backup',
            'broker_route_generation': '7',
        }, expected=request)


def test_normalize_broker_update_rejects_mismatched_route_generation():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
        broker_account_id='acct-42', broker_route='upstox-primary',
        broker_route_generation='7',
    )
    with pytest.raises(ValueError, match='broker route generation does not match request'):
        normalize_broker_update({
            'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
            'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
            'broker_account_id': 'acct-42', 'broker_route': 'upstox-primary',
            'broker_route_generation': '8',
        }, expected=request)


def test_normalize_broker_update_accepts_matching_route_identity():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
        broker_account_id='acct-42', broker_route='upstox-primary',
        broker_route_generation='7',
    )
    result = normalize_broker_update({
        'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
        'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
        'broker_account_id': 'acct-42', 'broker_route': 'upstox-primary',
        'broker_route_generation': '7',
    }, expected=request)
    assert result.broker_account_id == 'acct-42'
    assert result.broker_route == 'upstox-primary'
    assert result.broker_route_generation == '7'


def test_normalize_broker_update_rejects_quantity_mismatch_when_request_is_scoped():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
    )
    with pytest.raises(ValueError, match='broker quantity does not match request'):
        normalize_broker_update({
            'order_id': 'b1', 'status': 'NEW', 'quantity': 9,
            'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
        }, expected=request)


def test_normalize_broker_update_accepts_exact_requested_quantity():
    request = BrokerOrderRequest(
        client_order_id='c1', symbol='NIFTY', side='BUY', quantity=10,
    )
    result = normalize_broker_update({
        'order_id': 'b1', 'status': 'NEW', 'quantity': 10,
        'client_order_id': 'c1', 'symbol': 'NIFTY', 'side': 'BUY',
    }, expected=request)
    assert result.quantity == 10


def test_order_request_rejects_invalid_side_and_order_type():
    with pytest.raises(ValueError, match='side must be BUY or SELL'):
        BrokerOrderRequest('c1', 'NIFTY', 'HOLD', 10)
    with pytest.raises(ValueError, match='unsupported order_type'):
        BrokerOrderRequest('c1', 'NIFTY', 'BUY', 10, order_type='TRAILING')


def test_order_request_rejects_limit_without_positive_price():
    with pytest.raises(ValueError, match='LIMIT order requires a positive price'):
        BrokerOrderRequest('c1', 'NIFTY', 'BUY', 10, order_type='LIMIT')
    with pytest.raises(ValueError, match='LIMIT order requires a positive price'):
        BrokerOrderRequest('c1', 'NIFTY', 'BUY', 10, order_type='LIMIT', price=0)


def test_order_request_rejects_stop_orders_without_trigger_semantics():
    with pytest.raises(ValueError, match='SL order requires a positive trigger_price'):
        BrokerOrderRequest('c1', 'NIFTY', 'BUY', 10, order_type='SL', price=100)
    with pytest.raises(ValueError, match='SL-M order requires a positive trigger_price'):
        BrokerOrderRequest('c1', 'NIFTY', 'BUY', 10, order_type='SL-M')


def test_order_request_rejects_market_price_and_trigger_price():
    with pytest.raises(ValueError, match='MARKET order cannot specify a non-zero price'):
        BrokerOrderRequest('c1', 'NIFTY', 'BUY', 10, price=100)
    with pytest.raises(ValueError, match='MARKET order cannot specify trigger_price'):
        BrokerOrderRequest('c1', 'NIFTY', 'BUY', 10, trigger_price=100)


def test_order_request_accepts_valid_limit_and_stop_orders():
    limit = BrokerOrderRequest('c1', 'NIFTY', 'BUY', 10, order_type='LIMIT', price=100)
    sl = BrokerOrderRequest('c2', 'NIFTY', 'SELL', 10, order_type='SL', price=99, trigger_price=100)
    slm = BrokerOrderRequest('c3', 'NIFTY', 'SELL', 10, order_type='SL-M', trigger_price=100)
    assert limit.price == 100
    assert sl.trigger_price == 100
    assert slm.trigger_price == 100
