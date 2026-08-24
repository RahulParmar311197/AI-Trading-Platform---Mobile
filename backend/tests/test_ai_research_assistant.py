import pytest
from app.ai_research_assistant import AIResearchAssistant, AIResearchError


def test_research_requires_evidence():
    result = AIResearchAssistant().research("Is setup strong?", {"facts": ["MSS confirmed", "RR=2"]})
    assert "MSS confirmed" in result.evidence
    assert result.evidence_packet["facts"]


def test_empty_question_fails_closed():
    with pytest.raises(AIResearchError):
        AIResearchAssistant().research("", {"facts": ["x"]})
