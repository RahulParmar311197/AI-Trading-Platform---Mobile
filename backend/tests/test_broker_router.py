import time
from datetime import datetime, timedelta

import pytest

from app.broker_adapter import PaperBrokerAdapter, BrokerOrderRequest
from app.broker_execution_context import BrokerExecutionContext
from app.broker_order_snapshot import BrokerOrderSnapshot
from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_snapshot import BrokerSnapshot
from app.reconciliation import ReconciliationEngine
from app.safety_state import SafetyStateStore
from app.submission_intent_store import SubmissionIntentStore


def test_default_route_submits():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter())],'paper', safety_store=None)
    with pytest.raises(RuntimeError, match='TRADING_HALTED'):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))


def test_disabled_route_rejected():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter(),False)],'paper')
    with pytest.raises(ValueError):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))


def _ready_router(tmp_path, max_age=2.0):
    store=SafetyStateStore(str(tmp_path/'safety.json'))
    intents=SubmissionIntentStore(str(tmp_path/'intents.json'))
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter())],'paper', safety_store=store, max_reconciliation_age_seconds=max_age, submission_intent_store=intents)
    return router, store


def _verified_result_after_halt(store, router, *, generation=1, account_id='paper', route='paper', route_generation='paper-1'):
    halted=store.halt('reconcile')
    check=router.reconciliation_engine.check([], [], [], [])
    observed=datetime.fromisoformat(check.checked_at)
    fingerprint=router._current_snapshot_fingerprint(router.get(route))
    context=BrokerExecutionContext(account_id=account_id, broker_route=route, route_generation=route_generation, generation=generation, snapshot_fingerprint=fingerprint, observed_at=observed)
    reconciled_at=max(halted.halted_at + timedelta(seconds=0.001), observed)
    return router.reconciliation_engine.build_verified_result(check, context=context, reconciled_at=reconciled_at, open_orders_reconciled=True, positions_reconciled=True, submission_intents_resolved=0, broker_ready=True)


def _clear_with_current_reconciliation(store, router=None):
    result=_verified_result_after_halt(store, router)
    store.clear(result, active_context=result.context)


def test_router_and_reconciliation_share_the_same_intent_store(tmp_path):
    router, _ = _ready_router(tmp_path)
    assert router.reconciliation_engine.submission_intent_store is router.submission_intent_store


def test_router_rejects_engine_bound_to_different_intent_store(tmp_path):
    store=SafetyStateStore(str(tmp_path/'safety.json'))
    intents_a=SubmissionIntentStore(str(tmp_path/'a.json'))
    intents_b=SubmissionIntentStore(str(tmp_path/'b.json'))
    engine=ReconciliationEngine(intents_a)
    with pytest.raises(ValueError, match='same intent store'):
        BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter())],'paper', safety_store=store, submission_intent_store=intents_b, reconciliation_engine=engine)


def test_default_router_reconciliation_engine_is_durable(tmp_path):
    router, _ = _ready_router(tmp_path)
    assert isinstance(router.reconciliation_engine.submission_intent_store, SubmissionIntentStore)


def test_cancel_allowed_when_halted(tmp_path):
    router, store = _ready_router(tmp_path)
    broker = router.get('paper').adapter
    created = broker.submit_order(BrokerOrderRequest('c1','NIFTY','BUY',1))
    store.halt('test halt')
    cancelled = router.cancel(created['order_id'])
    assert cancelled['status'] == 'CANCELLED'


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


def test_existing_client_order_identity_fails_closed(tmp_path):
    router, store=_ready_router(tmp_path)
    _clear_with_current_reconciliation(store, router)
    request=BrokerOrderRequest('c1','NIFTY','BUY',1)
    first=router.submit(request)
    assert first['order_id']
    with pytest.raises(RuntimeError, match='broker order already exists'):
        router.submit(request)
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
    result=_verified_result_after_halt(store, router, generation=1, account_id='7', route='live', route_generation='g2')
    store.clear(result, active_context=result.context)
    with pytest.raises(RuntimeError, match='generation is not reconciled'):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1,broker_route='live'))


def test_stale_reconciliation_timestamp_blocks_submission(tmp_path):
    router, store = _ready_router(tmp_path, max_age=0.01)
    _clear_with_current_reconciliation(store, router)
    time.sleep(0.03)
    with pytest.raises(RuntimeError, match='reconciliation is stale'):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))


def test_fresh_reconciliation_allows_submission(tmp_path):
    router, store = _ready_router(tmp_path, max_age=2.0)
    _clear_with_current_reconciliation(store, router)
    order = router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))
    assert order['order_id']


def test_immediate_broker_state_change_blocks_submission(tmp_path):
    router, store = _ready_router(tmp_path)
    _clear_with_current_reconciliation(store, router)
    broker = router.get('paper').adapter
    original_get_orders = broker.get_orders
    calls = {'count': 0}

    def get_orders_with_external_change():
        calls['count'] += 1
        if calls['count'] == 3:
            broker._orders['external'] = {'order_id':'external','broker_order_id':'external','client_order_id':'manual-1','symbol':'NIFTY','side':'BUY','quantity':1,'filled_quantity':0,'status':'OPEN'}
        return original_get_orders()

    broker.get_orders = get_orders_with_external_change
    with pytest.raises(RuntimeError, match='immediately before submission'):
        router.submit(BrokerOrderRequest('c1','NIFTY','BUY',1))
    assert 'c1' not in broker._orders


def test_invalid_reconciliation_age_configuration_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='positive'):
        _ready_router(tmp_path, max_age=0)


class IncompleteOrderSnapshotBroker(PaperBrokerAdapter):
    def get_order_snapshot(self):
        return BrokerOrderSnapshot(orders=self.get_orders(), complete=False, source='incomplete-test')


class RecoveryPayloadBroker(PaperBrokerAdapter):
    def submit_order(self, order):
        self._orders['recovered']={'order_id':'recovered','broker_order_id':'recovered','client_order_id':order.client_order_id,'status':'OPEN'}
        raise RuntimeError('simulated submission transport failure')


def test_reconciliation_fingerprint_requires_authoritative_order_snapshot():
    router=BrokerRouter([BrokerRoute('paper',IncompleteOrderSnapshotBroker())],'paper')
    with pytest.raises(RuntimeError, match='not authoritative'):
        router._current_snapshot_fingerprint(router.get('paper'))


def test_reconciliation_snapshot_contains_route_and_account_identity():
    router=BrokerRouter([BrokerRoute('paper',PaperBrokerAdapter(),broker_account_id=17)],'paper')
    snapshot=router.get_snapshot('paper')
    assert isinstance(snapshot, BrokerSnapshot)
    assert snapshot.broker_route == 'paper'
    assert snapshot.broker_account_id == 17


def test_unresolved_submission_intent_zero_match_remains_unresolved(tmp_path):
    router, store=_ready_router(tmp_path)
    store.halt('recovery')
    intent=router.submission_intent_store.create(client_order_id='missing-client', route='paper', account_id=None, symbol='NIFTY', side='BUY', quantity=1, request_fingerprint='fp')
    assert intent.client_order_id == 'missing-client'
    assert router.reconcile_unresolved_submission_intents('paper') == []
    assert router.submission_intent_store.unresolved_count() == 1
    assert store.load().trading_halted is True


def test_unresolved_submission_intent_blocks_submission_even_if_safety_state_is_cleared(tmp_path):
    router, store=_ready_router(tmp_path)
    _clear_with_current_reconciliation(store, router)
    router.submission_intent_store.create(client_order_id='pending-client', route='paper', account_id=None, symbol='NIFTY', side='BUY', quantity=1, request_fingerprint='fp')
    with pytest.raises(RuntimeError, match='unresolved submission intents remain'):
        router.submit(BrokerOrderRequest('c2','NIFTY','BUY',1))
    assert store.load().trading_halted is True


def test_submit_recovery_rejects_incomplete_broker_payload(tmp_path):
    router, store = _ready_router(tmp_path)
    _clear_with_current_reconciliation(store, router)
    recovery = RecoveryPayloadBroker()
    router.routes['paper'] = BrokerRoute('paper', recovery)
    fingerprint = router._current_snapshot_fingerprint(router.get('paper'))
    state = store.load()
    state.broker_snapshot_fingerprint = fingerprint
    store.save(state)
    with pytest.raises(RuntimeError, match='recovery payload is incomplete'):
        router.submit(BrokerOrderRequest('c-recover','NIFTY','BUY',1))
    assert store.load().trading_halted is True
