import pytest
from app.ai_trade_explainer import AITradeExplainer, TradeExplanationError


def record():
    return {"decision":"REJECTED","signal":{"reasons":["SMC=0.20","TA=0.10"]},"risk":{"gates":["RR_BELOW_MINIMUM"]}}


def test_local_explanation_is_grounded():
    result = AITradeExplainer().explain(record())
    assert result.decision == "REJECTED"
    assert "SMC=0.20" in result.evidence
    assert "RR_BELOW_MINIMUM" in result.risk_gates


def test_missing_decision_fields_fail_closed():
    with pytest.raises(TradeExplanationError):
        AITradeExplainer().explain({"decision":"REJECTED"})
