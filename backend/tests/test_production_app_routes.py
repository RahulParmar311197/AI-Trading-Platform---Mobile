from app.main import app


def test_production_app_exposes_live_order_execution_route():
    routes = {(route.path, tuple(sorted(route.methods or ()))) for route in app.routes}

    assert any(path == "/api/orders" and "POST" in methods for path, methods in routes)
