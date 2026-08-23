from app.order_lifecycle import OrderLifecycle,OrderStatus
from app.order_reconciliation import OrderReconciler,BrokerOrder,ReconciliationAction

def test_missing_remote_order_is_created_locally():
    book=OrderLifecycle(); r=OrderReconciler(book)
    events=r.reconcile([BrokerOrder('b1','NIFTY','BUY',10,OrderStatus.FILLED,10,100.0)])
    assert events[0].action==ReconciliationAction.CREATE
    assert book.orders['b1'].filled_quantity==10

def test_duplicate_broker_update_is_alerted():
    book=OrderLifecycle(); r=OrderReconciler(book)
    remote=BrokerOrder('b1','NIFTY','BUY',10,OrderStatus.FILLED,10,100.0)
    events=r.reconcile([remote,remote])
    assert events[1].action==ReconciliationAction.ALERT

def test_already_synced_order_is_noop():
    book=OrderLifecycle(); book.create('b1','NIFTY','BUY',10); book.transition('b1',OrderStatus.FILLED,10,100.0)
    events=OrderReconciler(book).reconcile([BrokerOrder('b1','NIFTY','BUY',10,OrderStatus.FILLED,10,100.0)])
    assert events[0].action==ReconciliationAction.NOOP
