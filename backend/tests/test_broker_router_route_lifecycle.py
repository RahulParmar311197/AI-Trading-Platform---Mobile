import threading

from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.safety_state import SafetyStateStore


def test_route_lifecycle_lock_waits_for_inflight_submission(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    adapter = PaperBrokerAdapter()
    entered = threading.Event()
    release = threading.Event()

    def blocked_submit(request):
        entered.set()
        assert release.wait(timeout=2)
        return adapter.__class__.submit_order(adapter, request)

    adapter.submit_order = blocked_submit
    router = BrokerRouter([BrokerRoute("upstox:account:42", adapter, broker_account_id=42)], "upstox:account:42", safety_store=store)
    request = BrokerOrderRequest("client-1", "NIFTY", "BUY", 1, broker_route="upstox:account:42", broker_account_id=42)
    submission_done = threading.Event()
    replacement_done = threading.Event()

    def submit():
        router.submit(request)
        submission_done.set()

    def replace_route():
        with router.route_lifecycle_lock():
            router.routes["upstox:account:42"] = BrokerRoute("upstox:account:42", PaperBrokerAdapter(), broker_account_id=42)
        replacement_done.set()

    submit_thread = threading.Thread(target=submit)
    submit_thread.start()
    assert entered.wait(timeout=2)

    replacement_thread = threading.Thread(target=replace_route)
    replacement_thread.start()

    assert not replacement_done.wait(timeout=0.2)
    assert router.routes["upstox:account:42"].adapter is adapter

    release.set()
    assert submission_done.wait(timeout=2)
    assert replacement_done.wait(timeout=2)
    submit_thread.join(timeout=2)
    replacement_thread.join(timeout=2)

    assert router.routes["upstox:account:42"].adapter is not adapter
