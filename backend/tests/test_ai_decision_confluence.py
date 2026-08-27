from app.ai_decision_engine import AIDecisionEngine, DecisionConfig
from app.signal_confluence import SignalDecision
from backend.tests.test_ai_decision_engine import complete_indicators, context


def test_bullish_confluence_is_added_to_bullish_score():
    base = AIDecisionEngine(DecisionConfig(confluence_weight=0.0)).decide(
        context(indicators=complete_indicators())
    )
    with_confluence = AIDecisionEngine(DecisionConfig(confluence_weight=1.0)).decide(
        context(indicators=complete_indicators()),
        confluence=SignalDecision("BUY", 0.9, "LONG", ("agreement",), {"ict": 1.0, "technical": 1.0}),
    )
    assert with_confluence.bullish_score > base.bullish_score
    assert any("confluence BUY" in reason for reason in with_confluence.reasons)


def test_confluence_weight_zero_preserves_existing_scores():
    engine = AIDecisionEngine(DecisionConfig(confluence_weight=0.0))
    without = engine.decide(context(indicators=complete_indicators()))
    with_confluence = engine.decide(
        context(indicators=complete_indicators()),
        confluence=SignalDecision("SELL", 1.0, "SHORT", (), {"ict": 1.0, "technical": 1.0}),
    )
    assert with_confluence.bullish_score == without.bullish_score
    assert with_confluence.bearish_score == without.bearish_score


def test_invalid_confluence_weight_is_rejected():
    try:
        DecisionConfig(confluence_weight=1.1)
        raise AssertionError("invalid confluence weight accepted")
    except ValueError:
        pass
