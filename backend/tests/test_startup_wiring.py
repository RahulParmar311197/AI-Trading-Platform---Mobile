import importlib


def test_main_exposes_broker_recovery():
    module = importlib.import_module("app.main")
    assert module.broker_router is not None
    assert module.broker_recovery is not None
    assert module.recovery_manager is not None


def test_default_broker_route_is_paper(monkeypatch):
    monkeypatch.delenv("BROKER_ROUTE", raising=False)
    monkeypatch.delenv("DHAN_LIVE_ENABLED", raising=False)
    factory = importlib.import_module("app.broker_factory")
    router = factory.build_broker_router()
    assert router.default_route == "paper"
    assert router.get().name == "paper"
