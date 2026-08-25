from app.main import app


def test_authenticated_broker_accounts_api_is_registered():
    routes = {(route.path, tuple(sorted(route.methods or ()))) for route in app.routes}

    assert any(path == "/broker-accounts" and "POST" in methods for path, methods in routes)
    assert any(path == "/broker-accounts" and "GET" in methods for path, methods in routes)
    assert any(path == "/broker-accounts/{account_id}" and "DELETE" in methods for path, methods in routes)
