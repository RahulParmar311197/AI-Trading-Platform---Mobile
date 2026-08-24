from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_performance_endpoint():
    response = client.post("/api/ai/intelligence/performance", json={"trades":[{"pnl":100},{"pnl":-50}]})
    assert response.status_code == 200
    assert response.json()["total_trades"] == 2


def test_research_endpoint_requires_question():
    response = client.post("/api/ai/intelligence/research", json={"question":"","evidence_packet":{}})
    assert response.status_code == 422
