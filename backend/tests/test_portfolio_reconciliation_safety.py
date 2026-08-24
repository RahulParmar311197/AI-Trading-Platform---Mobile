from app.broker_adapter import PaperBrokerAdapter, BrokerOrderRequest


def snapshot(broker):
    return {p['symbol']: p['quantity'] for p in broker.get_positions()}


def test_matching_broker_and_local_positions_have_zero_mismatch():
    broker = PaperBrokerAdapter()
    order = broker.submit_order(BrokerOrderRequest('recon-1', 'NIFTY', 'BUY', 10))
    broker.fill_order(order.order_id, 10, 100)
    local = {'NIFTY': 10}
    remote = snapshot(broker)
    mismatches = {s: (local.get(s, 0), remote.get(s, 0)) for s in set(local) | set(remote) if local.get(s, 0) != remote.get(s, 0)}
    assert mismatches == {}


def test_position_mismatch_is_detected_fail_closed():
    broker = PaperBrokerAdapter()
    order = broker.submit_order(BrokerOrderRequest('recon-2', 'NIFTY', 'BUY', 10))
    broker.fill_order(order.order_id, 10, 100)
    local = {'NIFTY': 7}
    remote = snapshot(broker)
    mismatches = {s: (local.get(s, 0), remote.get(s, 0)) for s in set(local) | set(remote) if local.get(s, 0) != remote.get(s, 0)}
    assert mismatches == {'NIFTY': (7, 10)}


def test_remote_only_position_is_detected():
    broker = PaperBrokerAdapter()
    order = broker.submit_order(BrokerOrderRequest('recon-3', 'BANKNIFTY', 'SELL', 5))
    broker.fill_order(order.order_id, 5, 200)
    local = {}
    remote = snapshot(broker)
    mismatches = {s: (local.get(s, 0), remote.get(s, 0)) for s in set(local) | set(remote) if local.get(s, 0) != remote.get(s, 0)}
    assert mismatches == {'BANKNIFTY': (0, -5)}
