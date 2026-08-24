"""Unified read-only facade for the AI trading-intelligence capabilities."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.ai_market_analyst import AIMarketAnalyst, MarketAnalystError
from app.ai_performance_analytics import AIPerformanceAnalytics
from app.ai_research_assistant import AIResearchAssistant, AIResearchError
from app.ai_setup_analytics import AISetupAnalytics
from app.ai_trade_explainer import AITradeExplainer, TradeExplanationError
from app.ai_trading_journal import AITradingJournal

router = APIRouter(prefix="/api/ai/intelligence", tags=["ai-intelligence"])

class ResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    evidence_packet: dict[str, Any]

class TradeExplainRequest(BaseModel):
    record: dict[str, Any]

class JournalRequest(BaseModel):
    record: dict[str, Any]

class PerformanceRequest(BaseModel):
    trades: list[dict[str, Any]]

class SetupRequest(BaseModel):
    trades: list[dict[str, Any]]

@router.post("/research")
def research(payload: ResearchRequest):
    try:
        result = AIResearchAssistant().research(payload.question, payload.evidence_packet)
        return {"question": result.question, "answer": result.answer, "evidence": result.evidence, "uncertainties": result.uncertainties, "follow_up_data": result.follow_up_data}
    except AIResearchError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.post("/trade-explanation")
def trade_explanation(payload: TradeExplainRequest):
    try:
        result = AITradeExplainer().explain(payload.record)
        return result.__dict__
    except TradeExplanationError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.post("/journal")
def journal(payload: JournalRequest):
    try:
        return AITradingJournal().create_entry(payload.record).__dict__
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.post("/performance")
def performance(payload: PerformanceRequest):
    return AIPerformanceAnalytics().analyze(payload.trades).__dict__

@router.post("/setups")
def setups(payload: SetupRequest):
    return AISetupAnalytics().analyze(payload.trades)
