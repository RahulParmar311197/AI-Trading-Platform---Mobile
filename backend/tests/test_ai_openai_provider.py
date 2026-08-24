import json

from app.ai_openai_provider import OpenAIStrategyProvider


class FakeResponses:
    def create(self, **kwargs):
        assert kwargs["text"]["format"]["type"] == "json_object"
        return type("Response", (), {"output_text": json.dumps({"name": "test", "conditions": [], "direction": "both"})})()


class FakeClient:
    responses = FakeResponses()


def test_provider_requests_structured_json():
    provider = OpenAIStrategyProvider(client=FakeClient(), model="test-model")
    result = provider.generate_structured("system", "user")
    assert result["name"] == "test"
