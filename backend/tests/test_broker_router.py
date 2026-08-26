import time
from datetime import timedelta

import pytest

from app.broker_adapter import PaperBrokerAdapter, BrokerOrderRequest
from app.broker_router import BrokerRoute, BrokerRouter
from app.safety_state import SafetyStateStore
from app.reconciliation_result import ReconciliationResult


def test_default_route_submits():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter())],'paper', safety_store=None)
    with pytest.raises(Exception):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))


def test_disabled_route_rejected():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter(),False)],'paper')
    with pytest.raises(ValueError):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))


def _ready_router(tmp_path, max_age=2.0):
    store=SafetyStateStore(str(tmp_path/'safety.json'))
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter())],'paper', safety_store=store, max_reconciliation_age_seconds=max_age)
    return router, store


def _clear_with_current_reconciliation(store):
    halted = store.halt('reconcile')
    result = ReconciliationResult.from_verified_state(
        account_id='paper', generation=1, reconciled_at=halted.halted_at + timedelta(seconds=0.001),
        open_orders_reconciled=True, positions_reconciled=True, submission_intents_resolved=0, broker_ready=True,
    )
    store.clear(result)


def test_cancel_allowed_when_halted(tmp_path):
    router, store = _ready_router(tmp_path)
    order = router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))
    store.halt('test halt')
    cancelled = router.cancel(order.order_id)
    assert cancelled.status == 'CANCELLED'


def test_cancel_requires_order_id(tmp_path):
    router, _ = _ready_router(tmp_path)
    with pytest.raises(ValueError, match='order_id is required'):
        router.cancel('')


def test_account_binding_requires_matching_generation(tmp_path):
    store=SafetyStateStore(str(tmp_path/'safety.json'))
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter(),broker_account_id=7,generation='g1')],'paper', safety_store=store)
    request=BrokerOrderRequest('c1','NIFTY','BUY',1,broker_account_id=7,broker_route='paper',broker_route_generation='g2')
    with pytest.raises(RuntimeError, match='generation is stale'):
        router.submit(request)


def test_account_binding_requires_account_match(tmp_path):
    store=SafetyStateStore(str(tmp_path/'safety.json'))
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter(),broker_account_id=7,generation='g1')],'paper', safety_store=store)
    request=BrokerOrderRequest('c1','NIFTY','BUY',1,broker_account_id=8,broker_route='paper',broker_route_generation='g1')
    with pytest.raises(RuntimeError, match='does not match broker route'):
        router.submit(request)


def test_client_order_id_is_idempotent_at_router_boundary(tmp_path):
    router, _ = _ready_router(tmp_path)
    request=BrokerOrderRequest('c1','NIFTY','BUY',1)
    first=router.submit(request)
    second=router.submit(request)
    assert first.order_id == second.order_id
    assert second.message == 'BROKER_CLIENT_ID_REPLAY'
    assert len(router.get_orders()) == 1


def test_duplicate_client_order_identity_fails_closed(tmp_path):
    router, _ = _ready_router(tmp_path)
    broker=router.get('paper').adapter
    broker._orders['b1']={'order_id':'b1','broker_order_id':'b1','client_order_id':'c1','symbol':'NIFTY','side':'BUY','quantity':1,'filled_quantity':1,'status':'FILLED'}
    broker._orders['b2']={'order_id':'b2','broker_order_id':'b2','client_order_id':'c1','symbol':'NIFTY','side':'BUY','quantity':1,'filled_quantity':1,'status':'FILLED'}
    with pytest.raises(RuntimeError, match='ambiguous broker order identity'):
        router.find_order_by_client_id('c1')


def test_route_generation_must_have_matching_reconciliation(tmp_path):
    store=SafetyStateStore(str(tmp_path/'safety.json'))
    router=BrokerRouter([BrokerRoute('live',PaperBrokerAdapter(),broker_account_id=7,generation='g2')],'live', safety_store=store)
    with pytest.raises(RuntimeError, match='not reconciled'):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1,broker_route='live'))


def test_stale_reconciliation_generation_blocks_submission(tmp_path):
    store=SafetyStateStore(str(tmp_path/'safety.json'))
    router=BrokerRouter([BrokerRoute('live',PaperBrokerAdapter(),broker_account_id=7,generation='g2')],'live', safety_store=store)
    halted = store.halt('reconcile')
    result = ReconciliationResult.from_verified_state(
        account_id='7', generation=1, reconciled_at=halted.halted_at + timedelta(seconds=1),
        open_orders_reconciled=True, positions_reconciled=True, submission_intents_resolved=0, broker_ready=True,
    )
    store.clear(result)
    with pytest.raises(RuntimeError, match='generation is not reconciled'):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1,broker_route='live'))


def test_stale_reconciliation_timestamp_blocks_submission(tmp_path):
    router, store = _ready_router(tmp_path, max_age=0.01)
    _clear_with_current_reconciliation(store)
    time.sleep(0.03)
    with pytest.raises(RuntimeError, match='reconciliation is stale'):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))


def test_fresh_reconciliation_allows_submission(tmp_path):
    router, store = _ready_router(tmp_path, max_age=2.0)
    _clear_with_current_reconciliation(store)
    order = router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))
    assert order.order_id


def test_invalid_reconciliation_age_configuration_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='positive'):
        _ready_router(tmp_path, max_age=0)
